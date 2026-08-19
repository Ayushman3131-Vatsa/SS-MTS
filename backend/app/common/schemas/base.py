from pydantic import BaseModel, ConfigDict


class StrictRequestModel(BaseModel):
    """Base for API request bodies.

    Silently ignoring misspelled or unexpected fields is unsafe at mutation
    boundaries: clients can believe a value was accepted when it was actually
    discarded. Response models intentionally do not inherit from this class.
    """

    model_config = ConfigDict(extra="forbid")
