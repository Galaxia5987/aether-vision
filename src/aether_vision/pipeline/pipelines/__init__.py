"""Built-in pipelines. Importing this package registers them.

To add a pipeline: create a module here, decorate the class with
``@register_pipeline`` and import the module below.
"""

from aether_vision.pipeline.pipelines import object_detection, passthrough

__all__ = ["object_detection", "passthrough"]
