"""MMOTU global image-category label IDs and their published class names."""

MMOTU_8_CLASSES = (
    "chocolate_cyst",
    "serous_cystadenoma",
    "teratoma",
    "theca_cell_tumor",
    "simple_cyst",
    "normal_ovary",
    "mucinous_cystadenoma",
    "high_grade_serous_cystadenocarcinoma",
)


def mmotu_class_name(class_id: int) -> str:
    if type(class_id) is not int or not 0 <= class_id < len(MMOTU_8_CLASSES):
        raise ValueError(f"MMOTU class ID must be an integer from 0 to 7, got {class_id!r}")
    return MMOTU_8_CLASSES[class_id]
