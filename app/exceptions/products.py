class InsufficientProductDataError(Exception):
    """Input has too little data to write a card without inventing facts."""

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        super().__init__(
            "Недостаточно данных для карточки: нужны характеристики или описание товара"
        )
