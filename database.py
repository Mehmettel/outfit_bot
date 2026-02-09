import sqlite3
from typing import List, Tuple, Optional
from datetime import datetime
from contextlib import contextmanager
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name: str = "bot_data.db"):
        self.db_name = db_name
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = None
        retries = 3  # Maximum retry attempts
        retry_delay = 1  # Retry wait time in seconds
        
        for attempt in range(retries):
            try:
                conn = sqlite3.connect(
                    self.db_name,
                    timeout=20,
                    isolation_level=None  # Automatic commit
                )
                conn.row_factory = sqlite3.Row
                yield conn
                break
                
            except sqlite3.Error as e:
                logger.error(f"Database connection error (Attempt {attempt + 1}/{retries}): {e}")
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
                
                if attempt < retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise
                    
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass

    def init_db(self):
        """Initialize database tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # User states table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_states (
                        user_id INTEGER PRIMARY KEY,
                        is_active BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # User preferences table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        user_id INTEGER PRIMARY KEY,
                        mode TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # User events table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_events (
                        user_id INTEGER PRIMARY KEY,
                        event TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Favorites table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        analysis TEXT NOT NULL,
                        mode TEXT NOT NULL DEFAULT 'general',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Last analysis table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS last_analysis (
                        user_id INTEGER PRIMARY KEY,
                        analysis TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def set_user_state(self, user_id: int, is_active: bool) -> bool:
        """Set user state"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_states (user_id, is_active, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                    is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                """, (user_id, is_active, is_active))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error setting user state: {e}")
            return False

    def get_user_state(self, user_id: int) -> bool:
        """Get user state"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT is_active FROM user_states WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return bool(result['is_active']) if result else False
        except sqlite3.Error as e:
            logger.error(f"Error getting user state: {e}")
            return False

    def set_user_preference(self, user_id: int, mode: Optional[str]) -> bool:
        """Set user preference"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_preferences (user_id, mode, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                    mode = ?,
                    updated_at = CURRENT_TIMESTAMP
                """, (user_id, mode, mode))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error setting user preference: {e}")
            return False

    def get_user_preference(self, user_id: int) -> Optional[str]:
        """Get user preference"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT mode FROM user_preferences WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result['mode'] if result else None
        except sqlite3.Error as e:
            logger.error(f"Error getting user preference: {e}")
            return None

    def set_user_event(self, user_id: int, event: str) -> bool:
        """Set user event"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO user_events (user_id, event, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                    event = ?,
                    updated_at = CURRENT_TIMESTAMP
                """, (user_id, event, event))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error setting user event: {e}")
            return False

    def get_user_event(self, user_id: int) -> Optional[str]:
        """Get user event"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT event FROM user_events WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result['event'] if result else None
        except sqlite3.Error as e:
            logger.error(f"Error getting user event: {e}")
            return None

    def add_favorite(self, user_id: int, analysis: str, mode: str) -> bool:
        """Add favorite"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO favorites (user_id, analysis, mode)
                    VALUES (?, ?, ?)
                """, (user_id, analysis, mode))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error adding favorite: {e}")
            return False

    def get_user_favorites(self, user_id: int) -> List[Tuple[int, str, str, str]]:
        """Get user favorites"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, analysis, mode, created_at
                    FROM favorites
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                """, (user_id,))
                return [(row['id'], row['analysis'], row['mode'], row['created_at']) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting favorites: {e}")
            return []

    def delete_favorite(self, favorite_id: int, user_id: int) -> bool:
        """Delete favorite"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM favorites
                    WHERE id = ? AND user_id = ?
                """, (favorite_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error deleting favorite: {e}")
            return False

    def delete_all_favorites(self, user_id: int) -> int:
        """Delete all favorites"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
                deleted_count = cursor.rowcount
                conn.commit()
                return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Error deleting all favorites: {e}")
            return 0

    def save_last_analysis(self, user_id: int, analysis: str) -> bool:
        """Save last analysis"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO last_analysis (user_id, analysis, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                    analysis = ?,
                    updated_at = CURRENT_TIMESTAMP
                """, (user_id, analysis, analysis))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Error saving last analysis: {e}")
            return False

    def get_last_analysis(self, user_id: int) -> Optional[str]:
        """Get last analysis"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT analysis FROM last_analysis WHERE user_id = ?", (user_id,))
                result = cursor.fetchone()
                return result['analysis'] if result else None
        except sqlite3.Error as e:
            logger.error(f"Error getting last analysis: {e}")
            return None 