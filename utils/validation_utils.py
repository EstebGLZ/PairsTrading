import math


class ValidationUtils:
    """
    Class containing utility methods for validation
    """

    @staticmethod
    def require_finite(name: str, value: float) -> None:
        """
        Check if the given value is a finite float
        :param name: The value's name
        :param value: The value to check
        :raises ValueError: if the given value is not a finite float
        """
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite.")

    @staticmethod
    def require_positive(name: str, value: float, strict: bool = True) -> None:
        """
        Check if the given value positive float
        :param name: The value's name
        :param value: The value to check
        :param strict: If the value must be strictly positive. Defaults to True
        :raises ValueError: if the given value is not a finite float or is negative
        """
        ValidationUtils.require_finite(name, value)

        if value < 0 or (strict and value <= 0):
            raise ValueError(f"{name} must be {"strictly" if strict else ""} positive.")
