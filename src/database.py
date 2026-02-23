"""
Modul Database untuk MySQL Caching
Implementasi cache untuk respons API dan hasil analisis
"""

import os
import mysql.connector
from mysql.connector import Error
from typing import Dict, Optional, List
import json
import logging
from datetime import datetime
import threading

# Konfigurasi logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lock threading untuk singleton
_db_lock = threading.Lock()


class DatabaseManager:
    """
    MySQL database manager untuk caching dan persistensi data
    """

    def __init__(
        self,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        port: int = 3306
    ):
        """
        Inisialisasi database manager

        Args:
            host: Host MySQL (default dari env)
            user: User MySQL (default dari env)
            password: Password MySQL (default dari env)
            database: Nama database (default dari env)
            port: Port MySQL (default 3306)
        """
        self.host = host or os.getenv("DB_HOST", "localhost")
        self.user = user or os.getenv("DB_USER", "root")
        self.password = password or os.getenv("DB_PASS", "")
        self.database = database or os.getenv("DB_NAME", "comtrade_db")
        self.port = port

        self.connection = None
        self._connect()

    def _connect(self):
        """Buat koneksi database"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                port=self.port
            )

            if self.connection.is_connected():
                logger.info(f"Connected to MySQL database: {self.database}")

        except Error as e:
            logger.error(f"Error connecting to MySQL: {e}")
            self.connection = None

    def ensure_connection(self):
        """Pastikan koneksi database aktif"""
        try:
            if not self.connection or not self.connection.is_connected():
                self._connect()
        except Error as e:
            logger.error(f"Connection check failed: {e}")
            self._connect()

    def initialize_schema(self):
        """
        Buat tabel jika belum ada
        
        Note: hs_codes and hs_sections tables have been removed.
        System now uses AI-based HS code classification instead of local database.
        Only 3 tables remain: commodity_searches, api_cache, analysis_results.
        """
        self.ensure_connection()

        if not self.connection:
            logger.error("Cannot initialize schema: no database connection")
            return False

        try:
            cursor = self.connection.cursor()

            # Tabel 1: Cache pencarian komoditas
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commodity_searches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_input VARCHAR(255) NOT NULL,
                    commodity_name VARCHAR(255),
                    raw_hs_code VARCHAR(10),
                    semi_hs_code VARCHAR(10),
                    finished_hs_code VARCHAR(10),
                    ai_extraction JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_input (user_input),
                    INDEX idx_commodity (commodity_name)
                )
            """)

            # Tabel 2: Cache respons API
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    cache_key VARCHAR(255) UNIQUE NOT NULL,
                    request_type VARCHAR(50),
                    hs_code VARCHAR(10),
                    response_data JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NULL,
                    INDEX idx_cache_key (cache_key),
                    INDEX idx_hs_code (hs_code),
                    INDEX idx_expires (expires_at)
                )
            """)

            # Tabel 3: Hasil analisis (diupdate untuk sistem optimasi)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    commodity_name VARCHAR(255),
                    raw_hs_code VARCHAR(10),
                    semi_hs_code VARCHAR(10),
                    finished_hs_code VARCHAR(10),
                    optimization_results JSON,
                    analysis_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_commodity (commodity_name),
                    INDEX idx_created (created_at)
                )
            """)

            self.connection.commit()
            logger.info("Database schema initialized successfully")
            return True

        except Error as e:
            logger.error(f"Error initializing schema: {e}")
            return False
        finally:
            cursor.close()

    def cache_commodity_search(
        self,
        user_input: str,
        ai_extraction: Dict,
        raw_hs_code: str,
        semi_hs_code: str,
        finished_hs_code: str
    ) -> bool:
        """
        Simpan hasil pencarian komoditas ke cache

        Args:
            user_input: Input asli dari user
            ai_extraction: Hasil ekstraksi AI
            raw_hs_code: Kode HS bahan mentah
            semi_hs_code: Kode HS setengah jadi
            finished_hs_code: Kode HS produk jadi

        Returns:
            True jika berhasil disimpan ke cache
        """
        self.ensure_connection()

        try:
            cursor = self.connection.cursor()

            query = """
                INSERT INTO commodity_searches
                (user_input, commodity_name, raw_hs_code, semi_hs_code, finished_hs_code, ai_extraction)
                VALUES (%s, %s, %s, %s, %s, %s)
            """

            values = (
                user_input,
                ai_extraction.get('commodity_name'),
                raw_hs_code,
                semi_hs_code,
                finished_hs_code,
                json.dumps(ai_extraction)
            )

            cursor.execute(query, values)
            self.connection.commit()

            logger.info(f"Cached commodity search: {user_input}")
            return True

        except Error as e:
            logger.error(f"Error caching commodity search: {e}")
            return False
        finally:
            cursor.close()

    def get_cached_commodity_search(self, user_input: str) -> Optional[Dict]:
        """
        Ambil hasil pencarian komoditas dari cache

        Args:
            user_input: Input user yang dicari

        Returns:
            Hasil cache atau None
        """
        self.ensure_connection()

        try:
            cursor = self.connection.cursor(dictionary=True)

            query = """
                SELECT * FROM commodity_searches
                WHERE user_input = %s
                ORDER BY created_at DESC
                LIMIT 1
            """

            cursor.execute(query, (user_input,))
            result = cursor.fetchone()

            if result:
                # Parse field JSON
                result['ai_extraction'] = json.loads(result['ai_extraction'])
                logger.info(f"Cache hit for: {user_input}")
                return result

            return None

        except Error as e:
            logger.error(f"Error getting cached search: {e}")
            return None
        finally:
            cursor.close()

    def cache_api_response(
        self,
        cache_key: str,
        request_type: str,
        hs_code: str,
        response_data: Dict,
        ttl_days: int = 30
    ) -> bool:
        """
        Cache API response

        Args:
            cache_key: Unique cache key
            request_type: Type of request (export/import)
            hs_code: HS code
            response_data: API response data
            ttl_days: Time to live in days

        Returns:
            True if cached successfully
        """
        self.ensure_connection()

        try:
            cursor = self.connection.cursor()

            # Hitung tanggal kadaluarsa
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(days=ttl_days)

            query = """
                INSERT INTO api_cache
                (cache_key, request_type, hs_code, response_data, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                response_data = VALUES(response_data),
                expires_at = VALUES(expires_at),
                created_at = CURRENT_TIMESTAMP
            """

            values = (
                cache_key,
                request_type,
                hs_code,
                json.dumps(response_data),
                expires_at
            )

            cursor.execute(query, values)
            self.connection.commit()

            logger.info(f"Cached API response: {cache_key}")
            return True

        except Error as e:
            logger.error(f"Error caching API response: {e}")
            return False
        finally:
            cursor.close()

    def get_cached_api_response(self, cache_key: str) -> Optional[Dict]:
        """
        Get cached API response

        Args:
            cache_key: Cache key to lookup

        Returns:
            Cached response or None
        """
        self.ensure_connection()

        try:
            cursor = self.connection.cursor(dictionary=True)

            query = """
                SELECT * FROM api_cache
                WHERE cache_key = %s
                AND expires_at > NOW()
            """

            cursor.execute(query, (cache_key,))
            result = cursor.fetchone()

            if result:
                response_data = json.loads(result['response_data'])
                logger.info(f"API cache hit: {cache_key}")
                return response_data

            return None

        except Error as e:
            logger.error(f"Error getting cached API response: {e}")
            return None
        finally:
            cursor.close()

    def save_analysis_result(self, analysis: Dict) -> bool:
        """
        Save analysis result to database

        Args:
            analysis: Analysis result dictionary

        Returns:
            True if saved successfully
        """
        self.ensure_connection()

        try:
            cursor = self.connection.cursor()

            query = """
                INSERT INTO analysis_results
                (commodity_name, raw_hs_code, semi_hs_code, finished_hs_code,
                 optimization_results, analysis_summary)
                VALUES (%s, %s, %s, %s, %s, %s)
            """

            values = (
                analysis.get('commodity_name'),
                analysis.get('raw_hs_code'),
                analysis.get('semi_hs_code'),
                analysis.get('finished_hs_code'),
                json.dumps(analysis.get('optimization_results', {})),
                analysis.get('analysis_summary')
            )

            cursor.execute(query, values)
            self.connection.commit()

            logger.info(f"Saved analysis result: {analysis.get('commodity_name')}")
            return True

        except Error as e:
            logger.error(f"Error saving analysis result: {e}")
            return False
        finally:
            cursor.close()


    # =================================================================
    # METODE USANG - Tabel HS Code dihapus (sekarang pakai AI)
    # Metode berikut untuk kompatibilitas mundur, mengembalikan kosong/None
    # =================================================================

    def get_all_sections(self) -> List[Dict]:
        """
        DEPRECATED: HS sections table removed. AI now provides HS codes directly.
        Returns empty list for backward compatibility.
        """
        logger.warning("get_all_sections() is deprecated - hs_sections table removed")
        return []

    def get_section_by_code(self, section_code: str) -> Optional[Dict]:
        """
        DEPRECATED: HS sections table removed. AI now provides HS codes directly.
        Returns None for backward compatibility.
        """
        logger.warning("get_section_by_code() is deprecated - hs_sections table removed")
        return None

    def classify_commodity_by_section(self, hscode: str) -> Optional[Dict]:
        """
        DEPRECATED: HS classification tables removed. AI now provides HS codes directly.
        Returns None for backward compatibility.
        """
        logger.warning("classify_commodity_by_section() is deprecated - hs_codes/hs_sections tables removed")
        return None

    def get_hs_codes_by_section(self, section_code: str, limit: int = 100) -> List[Dict]:
        """
        DEPRECATED: HS codes table removed. AI now provides HS codes directly.
        Returns empty list for backward compatibility.
        """
        logger.warning("get_hs_codes_by_section() is deprecated - hs_codes table removed")
        return []

    def close(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Entry context manager - pastikan koneksi aktif"""
        self.ensure_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - tutup koneksi"""
        self.close()
        return False  # Jangan suppress exception


# Instance singleton
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> Optional[DatabaseManager]:
    """
    Get or create database manager singleton (thread-safe)

    Returns:
        DatabaseManager instance or None if connection fails
    """
    global _db_manager

    if _db_manager is None:
        with _db_lock:  # Inisialisasi thread-safe
            if _db_manager is None:  # Pola double-check
                try:
                    _db_manager = DatabaseManager()
                    _db_manager.initialize_schema()
                except Exception as e:
                    logger.error(f"Failed to initialize database: {e}")
                    return None

    return _db_manager


