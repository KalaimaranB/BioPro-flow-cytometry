from typing import Protocol

from .transforms import TransformType


class ChannelInferenceStrategy(Protocol):
    """Strategy for inferring the default transformation for a channel."""

    def infer_transform(self, channel: str) -> TransformType:
        ...

class DefaultChannelInference:
    """Default logic: Linear for Scatter/Time, Biexponential for Fluorescence."""
    
    def infer_transform(self, channel: str) -> TransformType:
        if not channel:
            return TransformType.LINEAR
            
        is_fluo = not any(x in channel.upper() for x in ["FSC", "SSC", "TIME"])
        return TransformType.BIEXPONENTIAL if is_fluo else TransformType.LINEAR
