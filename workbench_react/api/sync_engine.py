# workbench/api/sync_engine.py
"""
Real-time sync engine for collaborative editing
Handles debouncing, batching, conflict resolution, and state sync
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('workbench.sync_engine')


class ChangeTracker:
    """Tracks pending changes and batches them for sync"""

    def __init__(self, batch_interval: int = 2000):  # 2 seconds
        self.batch_interval = batch_interval  # milliseconds
        self.pending_changes: List[Dict] = []
        self.last_sync_time = None

    def add_change(self, operation: str, block_id: str, data: Dict) -> None:
        """Add a change to pending queue"""
        change = {
            'operation': operation,
            'block_id': block_id,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
        }
        self.pending_changes.append(change)
        logger.info(f"[ChangeTracker] Added {operation} for {block_id}")

    def get_pending_changes(self) -> List[Dict]:
        """Get all pending changes"""
        return self.pending_changes.copy()

    def clear_pending(self) -> None:
        """Clear pending changes after successful sync"""
        self.pending_changes.clear()
        self.last_sync_time = datetime.utcnow()
        logger.info(f"[ChangeTracker] Cleared pending changes")

    def should_batch(self) -> bool:
        """Check if batch should be sent"""
        if not self.pending_changes:
            return False

        if self.last_sync_time is None:
            return len(self.pending_changes) >= 5  # Minimum 5 changes

        # Check if interval elapsed
        elapsed_ms = (datetime.utcnow() - self.last_sync_time).total_seconds() * 1000
        return elapsed_ms >= self.batch_interval


class ConflictResolver:
    """Handles conflict resolution in collaborative editing"""

    @staticmethod
    def resolve_position_conflict(
        local_position: int,
        remote_position: int,
        local_content_length: int,
        remote_content_length: int
    ) -> int:
        """Resolve position conflicts (Operational Transformation)"""
        # Simple OT: if content grew remotely, adjust local position
        if remote_content_length > local_content_length:
            diff = remote_content_length - local_content_length
            return min(local_position + diff, remote_content_length)
        return local_position

    @staticmethod
    def merge_properties(
        local_props: Dict,
        remote_props: Dict,
        local_timestamp: float,
        remote_timestamp: float
    ) -> Dict:
        """Merge property changes (Last-Write-Wins)"""
        merged = local_props.copy()

        for key, remote_value in remote_props.items():
            if key in local_props:
                # LWW: keep whichever was updated more recently
                if remote_timestamp >= local_timestamp:
                    merged[key] = remote_value
            else:
                merged[key] = remote_value

        logger.info(f"[ConflictResolver] Merged properties")
        return merged


class UserPresenceManager:
    """Manages active users and their cursors/selections"""

    def __init__(self):
        self.active_users: Dict[str, Dict] = {}

    def add_user(self, user_id: str, page_id: str) -> None:
        """Add user to active list"""
        self.active_users[user_id] = {
            'page_id': page_id,
            'joined_at': datetime.utcnow().isoformat(),
            'cursor_position': 0,
            'selected_block': None,
        }
        logger.info(f"[UserPresence] Added {user_id} to {page_id}")

    def remove_user(self, user_id: str) -> Optional[str]:
        """Remove user from active list"""
        if user_id in self.active_users:
            page_id = self.active_users[user_id]['page_id']
            del self.active_users[user_id]
            logger.info(f"[UserPresence] Removed {user_id}")
            return page_id
        return None

    def update_cursor(self, user_id: str, block_id: str, position: int) -> None:
        """Update user cursor position"""
        if user_id in self.active_users:
            self.active_users[user_id]['cursor_position'] = position
            self.active_users[user_id]['selected_block'] = block_id

    def get_page_users(self, page_id: str) -> List[Dict]:
        """Get all active users on a page"""
        return [
            {'user_id': uid, **data}
            for uid, data in self.active_users.items()
            if data['page_id'] == page_id
        ]

    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Get specific user info"""
        return self.active_users.get(user_id)


class SyncState:
    """Manages synchronization state and version tracking"""

    def __init__(self):
        self.version = 0
        self.last_ack_version = 0
        self.pending_ops: Dict[int, Dict] = {}

    def create_operation(self, op_type: str, data: Dict) -> Dict:
        """Create a versioned operation"""
        self.version += 1
        return {
            'version': self.version,
            'type': op_type,
            'data': data,
            'timestamp': datetime.utcnow().isoformat(),
        }

    def ack_operation(self, version: int) -> None:
        """Acknowledge successful operation"""
        self.last_ack_version = version
        if version in self.pending_ops:
            del self.pending_ops[version]
            logger.info(f"[SyncState] Acknowledged version {version}")

    def get_pending_operations(self) -> List[Dict]:
        """Get all unacknowledged operations"""
        return list(self.pending_ops.values())

    def has_pending(self) -> bool:
        """Check if there are pending operations"""
        return len(self.pending_ops) > 0
