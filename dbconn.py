
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool
from dataclasses import make_dataclass

dsn = "host=localhost dbname=examdb user=examdbo password=pass"
db_pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=dsn)


@contextmanager
def db_block():
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            yield RecordCursor(cur)
            conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        db_pool.putconn(conn)


class RecordCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, vars=None):
        self._cursor.execute(query, vars)

    def __iter__(self):
        field_names = [d[0] for d in self._cursor.description]
        self._dataclass = make_dataclass("Rec", field_names)
        return self

    def __next__(self):

        record = self._cursor.__next__()
        record = self._dataclass(*record)

        return record

    def fetch_first(self):
        """ 读取数据的第一条 """

        try:
            return iter(self).__next__()
        except StopIteration:
            return None
