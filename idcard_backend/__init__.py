"""School ID Card Backend package."""
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
