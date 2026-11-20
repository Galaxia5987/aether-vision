"""Owns the ntcore instance and its connection lifecycle."""

from __future__ import annotations

import logging
import threading
import time

import ntcore

from aether_vision.config.models import NetworkTablesConfig

_log = logging.getLogger(__name__)


class NetworkTablesClient:
    """Creates a dedicated NT instance (not the process default) so it can be torn down cleanly."""

    def __init__(self, config: NetworkTablesConfig) -> None:
        self._config = config
        self._instance: ntcore.NetworkTableInstance | None = None
        self._listener: int | None = None
        self._connected = threading.Event()

    @property
    def instance(self) -> ntcore.NetworkTableInstance:
        if self._instance is None:
            raise RuntimeError("NetworkTables client is not started")
        return self._instance

    @property
    def root(self) -> str:
        return f"/{self._config.root_table}"

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def start(self) -> None:
        if self._instance is not None:
            return
        instance = ntcore.NetworkTableInstance.create()
        self._listener = instance.addConnectionListener(True, self._on_connection)
        if self._config.mode == "server":
            instance.startServer()
            self._connected.set()
            _log.info("NetworkTables server started")
        else:
            instance.startClient4(self._config.identity)
            if self._config.server_address:
                instance.setServer(self._config.server_address)
                target = self._config.server_address
            else:
                instance.setServerTeam(self._config.team)
                target = f"team {self._config.team}"
            _log.info("NetworkTables client connecting to %s", target)
        self._instance = instance

    def _on_connection(self, event: ntcore.Event) -> None:
        info = event.data
        if not isinstance(info, ntcore.ConnectionInfo):
            return
        if event.is_(ntcore.EventFlags.kConnected):
            self._connected.set()
            _log.info("NetworkTables connected to %s:%d", info.remote_ip, info.remote_port)
        elif event.is_(ntcore.EventFlags.kDisconnected):
            if self._config.mode == "client":
                self._connected.clear()
            _log.warning("NetworkTables disconnected from %s", info.remote_ip)

    def flush(self) -> None:
        if self._instance is not None:
            self._instance.flush()

    def stop(self) -> None:
        instance, self._instance = self._instance, None
        if instance is None:
            return
        try:
            instance.flush()
            time.sleep(0.05)  # give the network thread a moment to send the last values
            if self._listener is not None:
                instance.removeListener(self._listener)
            if self._config.mode == "server":
                instance.stopServer()
            else:
                instance.stopClient()
        finally:
            ntcore.NetworkTableInstance.destroy(instance)
            self._connected.clear()
            _log.info("NetworkTables stopped")
