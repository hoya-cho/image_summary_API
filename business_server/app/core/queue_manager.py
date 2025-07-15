import asyncio
from collections import deque
from typing import Deque, Optional, List
from ..models.schemas import QueuedItem
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleQueueManager:
    def __init__(self):
        self.priority_queue: Deque[QueuedItem] = deque() 
        self.normal_queue: Deque[QueuedItem] = deque()   
        self._lock = asyncio.Lock() 
        logger.info("SimpleQueueManager initialized.")

    async def add_to_queue(self, item: QueuedItem):
        async with self._lock:
            if item.is_first_time_user:
                self.priority_queue.append(item)
                logger.info(f"Added item {item.request_id} (customer: {item.customer_id}) to PRIORITY queue. Size: {len(self.priority_queue)}")
            else:
                self.normal_queue.append(item)
                logger.info(f"Added item {item.request_id} (customer: {item.customer_id}) to NORMAL queue. Size: {len(self.normal_queue)}")
            return True

    async def get_from_queue(self) -> Optional[QueuedItem]:
        async with self._lock:
            if self.priority_queue:
                item = self.priority_queue.popleft()
                logger.info(f"Retrieved item {item.request_id} from PRIORITY queue. Remaining: {len(self.priority_queue)}")
                return item
            elif self.normal_queue:
                item = self.normal_queue.popleft()
                logger.info(f"Retrieved item {item.request_id} from NORMAL queue. Remaining: {len(self.normal_queue)}")
                return item
            logger.info("No items in any queue to retrieve.")
            return None

    async def get_queue_status(self) -> dict:
        async with self._lock:
            return {
                "priority_queue_size": len(self.priority_queue),
                "normal_queue_size": len(self.normal_queue),
                "total_items": len(self.priority_queue) + len(self.normal_queue)
            }

    def get_all_items_snapshot(self) -> List[QueuedItem]: 

        all_items = list(self.priority_queue) + list(self.normal_queue)
        logger.info(f"Snapshot taken: {len(all_items)} items in total.")
        return all_items

# Global instance of the queue manager
queue_manager = SimpleQueueManager()
