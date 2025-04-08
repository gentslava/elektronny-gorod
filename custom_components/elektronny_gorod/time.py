from datetime import datetime


class Time:
    def __init__(self) -> None:
        self.time: datetime = datetime.now()

    def get_timestamp(self) -> str:
        return f"{self.time.isoformat()[:-3]}Z"

    def get_simpletime(self) -> str:
        return f"{self.time.strftime("%Y%m%d%H%M%S")}"
