from sim_core.ports import GpsTransmitter, SpeedBearingDevice


class NullGpsTransmitter(GpsTransmitter):
    async def play_iq(self, iq_path: str) -> None:
        return

    async def stop(self) -> None:
        return


class NullSpeedBearingDevice(SpeedBearingDevice):
    async def set_speed_kmh(self, kmh: float) -> None:
        return

    async def set_bearing_deg(self, deg: float) -> None:
        return

    async def stop(self) -> None:
        return
