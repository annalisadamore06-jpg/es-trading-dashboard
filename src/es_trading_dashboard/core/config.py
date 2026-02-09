"""Configuration management using Pydantic Settings."""

import os
import random
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IBSettings(BaseSettings):
    """Interactive Brokers connection settings."""
    
    model_config = SettingsConfigDict(env_prefix="IB_")
    
    host: str = Field(default="127.0.0.1", description="TWS/Gateway host")
    port: int = Field(default=7497, description="TWS port (7497) or Gateway port (4001)")
    client_id: int = Field(
        default_factory=lambda: random.randint(1000, 9999),
        description="Unique client ID for IB connection"
    )
    timeout: int = Field(default=30, description="Connection timeout in seconds")
    readonly: bool = Field(default=True, description="Read-only mode (no trading)")


class DashboardSettings(BaseSettings):
    """Dashboard UI settings."""
    
    model_config = SettingsConfigDict(env_prefix="DASHBOARD_")
    
    refresh_interval: int = Field(default=1, description="Data refresh interval in seconds")
    theme: Literal["dark", "light"] = Field(default="dark")
    page_title: str = Field(default="ES Trading Dashboard")


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Environment
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    
    # Sub-settings
    ib: IBSettings = Field(default_factory=IBSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
