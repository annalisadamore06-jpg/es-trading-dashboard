"""IB Connection manager for ES Trading Dashboard.

Handles connection to Interactive Brokers TWS/Gateway with:
- Automatic clientId selection to avoid conflicts with ATAS
- Connection retry logic
- Graceful disconnection
"""

import asyncio
import logging
import random
from typing import Optional

from ib_insync import IB, Contract

from .config import Config
from .exceptions import (
    IBConnectionError,
    IBTimeoutError,
    ClientIdConflictError,
)

logger = logging.getLogger(__name__)


class IBConnection:
    """Manages connection to Interactive Brokers.
    
    Attributes:
        config: Configuration object with IB settings
        ib: ib_insync IB client instance
        _connected: Connection state flag
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize IB connection manager.
        
        Args:
            config: Configuration object. Uses default if not provided.
        """
        self.config = config or Config()
        self.ib = IB()
        self._connected = False
        self._current_client_id: Optional[int] = None
        
        # Setup event handlers
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error
    
    @property
    def connected(self) -> bool:
        """Check if connected to IB."""
        return self._connected and self.ib.isConnected()
    
    @property
    def client_id(self) -> Optional[int]:
        """Get current clientId."""
        return self._current_client_id
    
    def _get_random_client_id(self) -> int:
        """Generate random clientId in configured range.
        
        Returns:
            Random integer between CLIENT_ID_MIN and CLIENT_ID_MAX
        """
        return random.randint(
            self.config.CLIENT_ID_MIN,
            self.config.CLIENT_ID_MAX
        )
    
    def _on_connected(self):
        """Handle successful connection."""
        self._connected = True
        logger.info(
            f"Connected to IB: {self.config.IB_HOST}:{self.config.IB_PORT} "
            f"(clientId={self._current_client_id})"
        )
    
    def _on_disconnected(self):
        """Handle disconnection."""
        self._connected = False
        logger.warning("Disconnected from IB")
    
    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Contract):
        """Handle IB errors.
        
        Args:
            reqId: Request ID
            errorCode: IB error code
            errorString: Error description
            contract: Related contract (if any)
        """
        # Error 326: clientId already in use
        if errorCode == 326:
            logger.error(f"ClientId conflict: {errorString}")
            raise ClientIdConflictError(self._current_client_id or 0)
        
        # Log other errors
        if errorCode not in (2104, 2106, 2158):  # Info messages
            logger.error(f"IB Error {errorCode}: {errorString}")
    
    async def connect(self, max_retries: int = 3) -> bool:
        """Connect to IB with automatic clientId selection.
        
        Tries multiple clientIds if the first one is in use.
        
        Args:
            max_retries: Maximum connection attempts
            
        Returns:
            True if connected successfully
            
        Raises:
            IBConnectionError: If all connection attempts fail
            IBTimeoutError: If connection times out
        """
        for attempt in range(max_retries):
            try:
                self._current_client_id = self._get_random_client_id()
                
                logger.info(
                    f"Connecting to IB (attempt {attempt + 1}/{max_retries}, "
                    f"clientId={self._current_client_id})..."
                )
                
                await asyncio.wait_for(
                    self.ib.connectAsync(
                        host=self.config.IB_HOST,
                        port=self.config.IB_PORT,
                        clientId=self._current_client_id,
                        readonly=True
                    ),
                    timeout=self.config.IB_TIMEOUT
                )
                
                if self.ib.isConnected():
                    self._connected = True
                    return True
                    
            except asyncio.TimeoutError:
                logger.warning(f"Connection attempt {attempt + 1} timed out")
                if attempt == max_retries - 1:
                    raise IBTimeoutError(
                        "Connection timed out",
                        timeout=self.config.IB_TIMEOUT
                    )
                    
            except ClientIdConflictError:
                logger.warning(
                    f"ClientId {self._current_client_id} in use, trying another..."
                )
                continue
                
            except Exception as e:
                logger.error(f"Connection error: {e}")
                if attempt == max_retries - 1:
                    raise IBConnectionError(str(e))
        
        raise IBConnectionError("All connection attempts failed")
    
    async def disconnect(self):
        """Gracefully disconnect from IB."""
        if self.ib.isConnected():
            logger.info("Disconnecting from IB...")
            self.ib.disconnect()
            self._connected = False
            self._current_client_id = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
        return False
