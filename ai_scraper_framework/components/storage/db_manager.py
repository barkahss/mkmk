import uuid
from typing import Optional, Dict, Any, TYPE_CHECKING

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func # For count

# Import your models
from .database_models import Base, ScrapingTask, ScrapingResult
from ai_scraper_framework.core.logger import get_logger
from ai_scraper_framework.core.exceptions import DatabaseError

if TYPE_CHECKING:
    from ai_scraper_framework.core.config import ConfigurationManager

logger = get_logger(__name__)

class DatabaseManager:
    """
    Manages database interactions, including engine setup, session creation,
    and CRUD operations for SQLAlchemy models.
    """
    def __init__(self, config: 'ConfigurationManager'):
        """
        Initializes the DatabaseManager.

        Constructs the PostgreSQL DSN from configuration and sets up the
        async engine and session factory.

        Args:
            config (ConfigurationManager): The application's configuration manager.

        Raises:
            DatabaseError: If database configuration is missing or DSN cannot be formed.
        """
        self.config = config
        db_config = self.config.get("database")

        if not db_config:
            logger.error("Database configuration is missing.")
            raise DatabaseError("Database configuration section ('database') not found.")

        try:
            # Construct DSN (Data Source Name) for PostgreSQL
            # Example: postgresql+asyncpg://user:password@host:port/dbname
            self.dsn = (
                f"{db_config.get('engine', 'postgresql+asyncpg')}://"
                f"{db_config.get('username')}:{db_config.get('password')}"
                f"@{db_config.get('host')}:{db_config.get('port')}"
                f"/{db_config.get('dbname')}"
            )
            logger.info(f"Database DSN constructed: {self.dsn.replace(db_config.get('password', '****'), '****')}")
        except TypeError: # Handles if any of the .get() returns None and it's used in f-string part that expects str
            logger.error("One or more required database configuration parameters (username, password, host, port, dbname) are missing.", exc_info=True)
            raise DatabaseError("Incomplete database configuration. Ensure username, password, host, port, and dbname are set.")

        self.engine = create_async_engine(
            self.dsn,
            echo=db_config.get('echo', False), # Log SQL queries if echo is true
            pool_size=db_config.get('pool_size', 5), # From existing config
            # max_overflow=db_config.get('max_overflow', 10) # Example for further pool tuning
        )
        
        # Create an async session factory
        self.async_session = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=False, # Good practice for async sessions
            class_=AsyncSession # Explicitly use AsyncSession
        )
        logger.info("Async SQLAlchemy engine and session maker configured.")

    async def get_session(self) -> AsyncSession:
        """Provides an asynchronous database session."""
        async with self.async_session() as session:
            yield session
            
    async def create_db_and_tables(self):
        """
        Creates all database tables defined in Base.metadata.
        This is typically called once at application startup.
        """
        logger.info("Attempting to create database tables if they don't exist...")
        async with self.engine.begin() as conn:
            try:
                # await conn.run_sync(Base.metadata.drop_all) # Use with caution: drops all tables
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Database tables created successfully (or already exist).")
            except Exception as e:
                logger.error(f"Error creating database tables: {e}", exc_info=True)
                raise DatabaseError(f"Could not create database tables: {e}", original_exception=e)

    async def add_task(self, url: str) -> ScrapingTask:
        """
        Creates a new ScrapingTask, adds it to the session, commits, and returns the task.

        Args:
            url (str): The URL for the new scraping task.

        Returns:
            ScrapingTask: The newly created ScrapingTask object.
        
        Raises:
            DatabaseError: If there's an issue committing the session.
        """
        async with self.async_session() as session:
            async with session.begin():
                try:
                    new_task = ScrapingTask(url=url, status="pending")
                    session.add(new_task)
                    await session.flush() # To get ID before commit if needed, and for immediate feedback
                    await session.commit() # Commit the transaction
                    logger.info(f"New scraping task added for URL: {url}, Task ID: {new_task.id}")
                    return new_task
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error adding new task for URL '{url}': {e}", exc_info=True)
                    raise DatabaseError(f"Could not add task: {e}", original_exception=e)

    async def update_task_status(self, task_id: uuid.UUID, status: str) -> Optional[ScrapingTask]:
        """
        Updates the status for a ScrapingTask.
        Error information is stored in the associated ScrapingResult, not directly on the task.

        Args:
            task_id (uuid.UUID): The ID of the task to update.
            status (str): The new status for the task.

        Returns:
            Optional[ScrapingTask]: The updated ScrapingTask object, or None if not found.
        
        Raises:
            DatabaseError: If there's an issue committing the session.
        """
        async with self.async_session() as session:
            async with session.begin():
                try:
                    stmt = select(ScrapingTask).where(ScrapingTask.id == task_id)
                    result = await session.execute(stmt)
                    task_to_update = result.scalar_one_or_none()

                    if task_to_update:
                        task_to_update.status = status
                        # task_to_update.updated_at is handled by SQLAlchemy's onupdate
                        await session.commit()
                        logger.info(f"Task {task_id} status updated to '{status}'.")
                        return task_to_update
                    else:
                        logger.warning(f"Task with ID {task_id} not found for status update.")
                        return None
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error updating task {task_id} status: {e}", exc_info=True)
                    raise DatabaseError(f"Could not update task status: {e}", original_exception=e)

    async def add_scraping_result(
        self, 
        task_id: uuid.UUID, 
        data: Optional[Dict[str, Any]] = None, 
        error_info: Optional[str] = None, 
        screenshot_path: Optional[str] = None, 
        ocr_text: Optional[str] = None
    ) -> ScrapingResult:
        """
        Creates a ScrapingResult, links it to a task_id, adds, commits, and returns the result.

        Args:
            task_id (uuid.UUID): The ID of the parent ScrapingTask.
            data (Optional[Dict[str, Any]]): The scraped data (JSON serializable).
            error_info (Optional[str]): Error message if scraping failed.
            screenshot_path (Optional[str]): Path to the screenshot file.
            ocr_text (Optional[str]): Text extracted via OCR.

        Returns:
            ScrapingResult: The newly created ScrapingResult object.

        Raises:
            DatabaseError: If there's an issue committing the session or task_id not found.
        """
        async with self.async_session() as session:
            async with session.begin():
                try:
                    # Optional: Verify task_id exists
                    task_exists = await session.get(ScrapingTask, task_id)
                    if not task_exists:
                        logger.error(f"Cannot add result: Task with ID {task_id} not found.")
                        raise DatabaseError(f"Parent task with ID {task_id} not found.")

                    new_result = ScrapingResult(
                        task_id=task_id,
                        data=data,
                        error_info=error_info,
                        screenshot_file_path=screenshot_path,
                        ocr_extracted_text=ocr_text
                    )
                    session.add(new_result)
                    await session.flush() # To get ID before commit
                    await session.commit()
                    logger.info(f"Scraping result added for Task ID: {task_id}, Result ID: {new_result.id}")
                    return new_result
                except Exception as e:
                    await session.rollback()
                    logger.error(f"Error adding scraping result for task {task_id}: {e}", exc_info=True)
                    raise DatabaseError(f"Could not add scraping result: {e}", original_exception=e)

    async def get_task(self, task_id: uuid.UUID, load_results: bool = False) -> Optional[ScrapingTask]:
        """
        Retrieves a ScrapingTask by its ID.

        Args:
            task_id (uuid.UUID): The ID of the task to retrieve.
            load_results (bool): If True, eagerly load associated scraping results.

        Returns:
            Optional[ScrapingTask]: The ScrapingTask object if found, else None.
        """
        async with self.async_session() as session:
            try:
                stmt = select(ScrapingTask).where(ScrapingTask.id == task_id)
                if load_results:
                    stmt = stmt.options(selectinload(ScrapingTask.results))
                
                result = await session.execute(stmt)
                task = result.scalar_one_or_none()
                
                if task:
                    logger.debug(f"Task {task_id} retrieved. Results loaded: {load_results}")
                else:
                    logger.debug(f"Task {task_id} not found.")
                return task
            except Exception as e:
                logger.error(f"Error retrieving task {task_id}: {e}", exc_info=True)
                # Depending on policy, could re-raise or just return None.
                # For a get operation, returning None on error might be acceptable.
                return None

    async def get_tasks(self, skip: int = 0, limit: int = 20) -> Tuple[List[ScrapingTask], int]:
        """
        Retrieves a paginated list of ScrapingTasks and the total count of tasks.

        Args:
            skip (int): Number of tasks to skip (for pagination).
            limit (int): Maximum number of tasks to return.

        Returns:
            Tuple[List[ScrapingTask], int]: A tuple containing a list of ScrapingTask objects
                                            and the total number of tasks in the database.
        
        Raises:
            DatabaseError: If there's an issue querying the database.
        """
        async with self.async_session() as session:
            try:
                # Get total count
                count_stmt = select(func.count(ScrapingTask.id))
                total_count_result = await session.execute(count_stmt)
                total_tasks = total_count_result.scalar_one()

                # Get paginated tasks, ordered by creation date (most recent first)
                stmt = select(ScrapingTask).order_by(ScrapingTask.created_at.desc()).offset(skip).limit(limit)
                result = await session.execute(stmt)
                tasks = result.scalars().all()
                
                logger.debug(f"Retrieved {len(tasks)} tasks (skip={skip}, limit={limit}). Total tasks: {total_tasks}.")
                return tasks, total_tasks
            except Exception as e:
                logger.error(f"Error retrieving tasks with pagination (skip={skip}, limit={limit}): {e}", exc_info=True)
                raise DatabaseError(f"Could not retrieve tasks: {e}", original_exception=e)

    async def get_results_for_task(self, task_id: uuid.UUID) -> List[ScrapingResult]:
        """
        Retrieves all ScrapingResult objects associated with a specific ScrapingTask ID.
        Results are ordered by creation date (most recent first).

        Args:
            task_id (uuid.UUID): The ID of the parent ScrapingTask.

        Returns:
            List[ScrapingResult]: A list of ScrapingResult objects. Empty if no results found.
        
        Raises:
            DatabaseError: If there's an issue querying the database.
        """
        async with self.async_session() as session:
            try:
                stmt = select(ScrapingResult).where(ScrapingResult.task_id == task_id).order_by(ScrapingResult.created_at.desc())
                result = await session.execute(stmt)
                results = result.scalars().all()
                logger.debug(f"Retrieved {len(results)} results for task ID {task_id}.")
                return results
            except Exception as e:
                logger.error(f"Error retrieving results for task {task_id}: {e}", exc_info=True)
                raise DatabaseError(f"Could not retrieve results for task {task_id}: {e}", original_exception=e)
                
    async def get_result(self, result_id: uuid.UUID) -> Optional[ScrapingResult]:
        """
        Retrieves a ScrapingResult by its ID.

        Args:
            result_id (uuid.UUID): The ID of the result to retrieve.

        Returns:
            Optional[ScrapingResult]: The ScrapingResult object if found, else None.
        """
        async with self.async_session() as session:
            try:
                stmt = select(ScrapingResult).where(ScrapingResult.id == result_id)
                # Typically, when fetching a result, its parent task might be useful.
                stmt = stmt.options(selectinload(ScrapingResult.task))
                
                result = await session.execute(stmt)
                scraping_result = result.scalar_one_or_none()
                
                if scraping_result:
                    logger.debug(f"Result {result_id} retrieved.")
                else:
                    logger.debug(f"Result {result_id} not found.")
                return scraping_result
            except Exception as e:
                logger.error(f"Error retrieving result {result_id}: {e}", exc_info=True)
                return None

# Placeholder for __main__ block for basic testing if needed later.
# Requires an actual PostgreSQL database running and configured.
# Example:
# if __name__ == "__main__":
#     from ai_scraper_framework.core.config import config_manager
#     # Ensure config is loaded, e.g., development
#     config_manager.load_config("development") 
#     db_manager = DatabaseManager(config=config_manager)
#
#     async def run_tests():
#         await db_manager.create_db_and_tables()
#         # Add more tests here
#         task = await db_manager.add_task(url="http://example.com/db_test")
#         print(f"Added task: {task}")
#         if task:
#             res = await db_manager.add_scraping_result(task_id=task.id, data={"key": "value"})
#             print(f"Added result: {res}")
#             retrieved_task = await db_manager.get_task(task.id, load_results=True)
#             print(f"Retrieved task with results: {retrieved_task}, results: {retrieved_task.results if retrieved_task else None}")
#
#     asyncio.run(run_tests())
