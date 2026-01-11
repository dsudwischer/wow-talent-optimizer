from pydantic import BaseModel, Field, ConfigDict


class Spell(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    spell_id: int = Field(alias="spellId")
    name: str
    max_ranks: int = Field(alias="maxRanks")


class SpecNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    previous_node_ids: list[int] = Field(alias="previousNodeIds")
    row: int
    column: int
    spells: list[Spell]


class RowCheckpoint(BaseModel):
    row: int
    points: int


class Spec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    spec_nodes: dict[str, SpecNode] = Field(alias="specNodes")
    spec_checkpoints: list[RowCheckpoint] = Field(alias="specCheckpoints")


class Class(BaseModel):
    name: str
    specs: dict[str, Spec]
