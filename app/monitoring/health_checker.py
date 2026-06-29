import os
import time
from app.utils.logger import logger
from app.config import settings

try:
    import psutil
except ImportError:
    psutil = None

class HealthChecker:
    """
    Monitors system resources (CPU, RAM, Disk) to ensure the 
    trading bot operates in a healthy environment.
    """
    def __init__(self):
        self.max_cpu_percent = 90.0
        self.max_ram_percent = 85.0
        self.min_disk_mb = 500.0

    def check_health(self) -> bool:
        """
        Returns True if system is healthy, False if critical resources are depleted.
        """
        if not psutil:
            return True # Can't check, assume healthy
            
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').free / (1024 * 1024) # MB
            
            is_healthy = True
            
            if cpu > self.max_cpu_percent:
                logger.warning(f"⚠️ High CPU Usage: {cpu}%")
                is_healthy = False
                
            if ram > self.max_ram_percent:
                logger.warning(f"⚠️ High RAM Usage: {ram}%")
                is_healthy = False
                
            if disk < self.min_disk_mb:
                logger.warning(f"⚠️ Low Disk Space: {disk:.2f} MB left")
                is_healthy = False
                
            return is_healthy
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

health_checker = HealthChecker()
