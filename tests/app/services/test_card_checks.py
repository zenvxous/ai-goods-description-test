from app.core.constants import NO_DATA
from app.schemas.products import ProductCard, ProductInput, SpecItem
from app.services.card_checks import check_card, extract_numbers, normalize, word_stems


def test_normalize_unifies_dashes_and_decimal_commas() -> None:
    assert normalize("0–1,6 МПа") == "0-1.6 мпа"


def test_extract_numbers() -> None:
    assert extract_numbers("0–1,6 МПа, G1/2, 100 мм") == {"0", "1.6", "1", "2", "100"}


def test_valid_card_has_no_issues(valid_card: ProductCard, product: ProductInput) -> None:
    assert check_card(valid_card, product) == []


def test_reformatted_numeric_value_is_accepted(
    valid_card: ProductCard, product: ProductInput
) -> None:
    valid_card.key_specs[0] = SpecItem(name="Диапазон измерений", value="от 0 до 1.6 МПа")

    assert check_card(valid_card, product) == []


def test_invented_spec_value_is_reported(valid_card: ProductCard, product: ProductInput) -> None:
    valid_card.key_specs.append(SpecItem(name="Степень защиты", value="IP65"))
    valid_card.key_specs.append(SpecItem(name="Материал корпуса", value="нержавеющая сталь"))

    issues = check_card(valid_card, product)

    assert any("Степень защиты" in issue and "65" in issue for issue in issues)
    assert any("Материал корпуса" in issue for issue in issues)


def test_no_data_value_is_accepted(valid_card: ProductCard, product: ProductInput) -> None:
    valid_card.key_specs.append(SpecItem(name="Масса", value=NO_DATA.upper()))

    assert check_card(valid_card, product) == []


def test_invented_number_in_text_is_reported(
    valid_card: ProductCard, product: ProductInput
) -> None:
    valid_card.commercial.tasks.append("Гарантия 3 года")

    issues = check_card(valid_card, product)

    assert issues == [
        "commercial: числа 3 отсутствуют во входных данных",
        "commercial.tasks: формулировки «гарантия» не подтверждаются входными данными",
    ]


def test_length_and_count_limits_are_reported(
    valid_card: ProductCard, product: ProductInput
) -> None:
    valid_card.seo_title = "Манометр " * 10
    valid_card.seo_description = "Манометр показывающий."
    valid_card.search_queries = ["манометр"]
    valid_card.key_specs = []

    issues = check_card(valid_card, product)

    assert len(issues) == 4
    assert issues[0].startswith("seo_title длиной 90")
    assert issues[1].startswith("seo_description длиной 22")
    assert issues[2].startswith("search_queries содержит 1")
    assert issues[3] == "key_specs пустой"


def test_unsupported_claims_are_reported(valid_card: ProductCard, product: ProductInput) -> None:
    valid_card.seo_description = valid_card.seo_description.replace(
        "предназначен", "надёжно предназначен", 1
    )
    valid_card.commercial.tasks.append("Работа в широком диапазоне условий")

    issues = check_card(valid_card, product)

    assert "seo_description: формулировки «надежно» не подтверждаются входными данными" in issues
    assert "commercial.tasks: формулировки «широком» не подтверждаются входными данными" in issues


def test_claim_present_in_input_is_accepted(valid_card: ProductCard) -> None:
    product = ProductInput(
        name="Манометр показывающий DM 02",
        manufacturer="Манотомь",
        specs={"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5"},
        description="Надёжный прибор для пищевой промышленности, G1/2, 100 мм.",
    )
    valid_card.seo_description = valid_card.seo_description.replace(
        "предназначен", "надежно предназначен для пищевой промышленности,", 1
    )

    assert check_card(valid_card, product) == []


def test_unmentioned_industry_is_reported(valid_card: ProductCard, product: ProductInput) -> None:
    valid_card.seo_description = valid_card.seo_description.replace(
        "предназначен", "в нефтегазовой отрасли предназначен", 1
    )

    issues = check_card(valid_card, product)

    assert issues == ["seo_description: отрасли «нефтегазовой» не упоминаются во входных данных"]


def test_unmentioned_industry_in_commercial_is_reported(
    valid_card: ProductCard, product: ProductInput
) -> None:
    valid_card.commercial.audience.append("Предприятия нефтегазовой отрасли")

    issues = check_card(valid_card, product)

    assert issues == ["commercial: отрасли «нефтегазовой» не упоминаются во входных данных"]


def test_inflected_text_value_is_accepted(valid_card: ProductCard) -> None:
    product = ProductInput(
        name="Манометр показывающий DM 02",
        manufacturer="Манотомь",
        specs={"диапазон измерений": "0–1,6 МПа", "класс точности": "1,5"},
        description="Показания считываются по круговой шкале со стрелочным указателем. "
        "Присоединение G1/2, корпус 100 мм.",
    )
    valid_card.key_specs.append(
        SpecItem(name="Индикация", value="Круговая шкала со стрелочным указателем")
    )

    assert check_card(valid_card, product) == []


def test_word_stems_ignore_endings_and_short_words() -> None:
    assert word_stems("по круговой шкале") == word_stems("круговая шкала")


def test_swapped_device_type_is_reported(valid_card: ProductCard, product: ProductInput) -> None:
    valid_card.search_queries.append("датчик давления Манотомь DM 02")

    issues = check_card(valid_card, product)

    assert issues == ["search_queries: тип прибора «датчик» не соответствует входным данным"]
