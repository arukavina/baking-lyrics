"""Baking Lyrics model package: data preparation, training, ONNX export and ONNX based generation.

Only `ml.tokenizer` and `ml.generate` are meant to be imported by the API at serving time.
They depend on the standard library, numpy and (lazily) onnxruntime, never on torch.
"""
