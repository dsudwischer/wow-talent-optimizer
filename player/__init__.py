import dataclasses


@dataclasses.dataclass(frozen=True)
class Player:
    name: str
    level: int
    race: str

    def get_available_spec_talent_points(self) -> int:
        match self.level:
            case 80:
                return 30
            case 90:
                return 34
        raise ValueError(f"Unsupported level: {self.level}")
