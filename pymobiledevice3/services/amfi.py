#!/usr/bin/env python3
import logging
import time

import construct

from pymobiledevice3.exceptions import AmfiError, ConnectionFailedError, DeveloperModeError, \
    DeviceHasPasscodeSetError, NoDeviceConnectedError, PyMobileDevice3Exception
from pymobiledevice3.lockdown import LockdownClient
from pymobiledevice3.services.heartbeat import HeartbeatService


class AmfiService:
    SERVICE_NAME = 'com.apple.amfi.lockdown'

    def __init__(self, lockdown: LockdownClient):
        self._lockdown = lockdown
        self._logger = logging.getLogger(self.__module__)

    def create_amfi_show_override_path_file(self):
        """ create an empty file at AMFIShowOverridePath """
        service = self._lockdown.start_service(self.SERVICE_NAME)
        resp = service.send_recv_plist({'action': 0})
        if not resp['status']:
            raise PyMobileDevice3Exception(f'create_AMFIShowOverridePath() failed with: {resp}')

    def enable_developer_mode(self, enable_post_restart=True):
        """
        enable developer-mode
        if enable_post_restart is True, then wait for device restart to answer the final prompt
        with "yes"
        """
        service = self._lockdown.start_service(self.SERVICE_NAME)
        resp = service.send_recv_plist({'action': 1})
        error = resp.get('Error')

        if error is not None:
            if error == 'Device has a passcode set':
                raise DeviceHasPasscodeSetError()
            raise AmfiError(error)

        if not resp.get('success'):
            raise DeveloperModeError(f'enable_developer_mode(): {resp}')

        if not enable_post_restart:
            return

        try:
            HeartbeatService(self._lockdown).start()
        except ConnectionAbortedError:
            self._logger.debug('device disconnected, awaiting reconnect')

        """
            Workaround to solve:
            "OSError: [WinError 10048] Only one usage of each socket address 
            (protocol/network address/port) is normally permitted" error
            https://github.com/doronz88/pymobiledevice3/issues/428

            We 
        """
        retries = 0
        max_retries = 60
        after_reset_lockdown = None
        while not after_reset_lockdown and retries <= max_retries:
            try:
                self._lockdown = LockdownClient(self._lockdown.udid)
                after_reset_lockdown = self._lockdown
                break
            except (NoDeviceConnectedError, ConnectionFailedError, construct.core.StreamError, OSError):
                self._logger.error(f"Waiting for lockdown using id: {self._lockdown.udid}. "
                                   f"Retries count: {retries}/{max_retries}")

            retries = retries + 1
            time.sleep(1)

        # We want the user to decide to "Turn on" or "Cancel" after the device has restarted
        # self.enable_developer_mode_post_restart()

    def enable_developer_mode_post_restart(self):
        """ answer the prompt that appears after the restart with "yes" """
        service = self._lockdown.start_service(self.SERVICE_NAME)
        resp = service.send_recv_plist({'action': 2})
        if not resp.get('success'):
            raise DeveloperModeError(f'enable_developer_mode_post_restart() failed: {resp}')
