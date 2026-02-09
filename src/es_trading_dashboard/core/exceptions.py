"""Custom exceptions for ES Trading Dashboard."""


class ESTradingError(Exception):
    """Base exception for ES Trading Dashboard."""
    pass


class IBConnectionError(ESTradingError):
    """Raised when connection to Interactive Brokers fails."""
    
    def __init__(self, message: str = "Failed to connect to Interactive Brokers"):
        self.message = message
        super().__init__(self.message)


class IBTimeoutError(ESTradingError):
    """Raised when IB request times out."""
    
    def __init__(self, message: str = "IB request timed out", timeout: float = 0):
        self.message = message
        self.timeout = timeout
        super().__init__(f"{self.message} (timeout: {timeout}s)")


class ConfigurationError(ESTradingError):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str = "Invalid configuration"):
        self.message = message
        super().__init__(self.message)


class ClientIdConflictError(IBConnectionError):
    """Raised when clientId is already in use (IB Error 326)."""
    
    def __init__(self, client_id: int):
        self.client_id = client_id
        super().__init__(f"ClientId {client_id} is already in use")


class MarketDataError(ESTradingError):
    """Raised when market data request fails."""
    
    def __init__(self, message: str = "Market data request failed", symbol: str = ""):
        self.message = message
        self.symbol = symbol
        super().__init__(f"{self.message}: {symbol}" if symbol else self.message)
