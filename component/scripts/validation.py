import pandas as pd
from component.parameter.reclassify_parameters import NO_VALUE, MATRIX_NAMES
from component.message import cm
from .scripts import set_transition_code


def read_file(file_, text_field_msg):
    """Read csv file and return a dataframe"""
    try:
        # Read csv file
        df = pd.read_csv(file_)
        # remove white spaces from column names

        # I cannot modify the dataframe
        # df.columns = df.columns.str.strip()

    except pd.errors.ParserError:
        # Raise a more specific error for when the file cannot be parsed as a csv
        error_msg = (
            "The file could not be read. Please check that the file is a valid csv file"
        )
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    except FileNotFoundError:
        # Raise a more specific error for when the file cannot be found
        error_msg = "The file could not be found. Please check the file path."
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    return df


def validate_transition_matrix(file_, text_field_msg):
    """Read user inputs from custom transition matrix and custom green/non green"""

    df = read_file(file_, text_field_msg)

    # Define column requirements for each type
    column_requirements = {
        "required_cols": ["from_code", "to_code", "impact_code"],
        "int_cols": ["from_code", "to_code", "impact_code"],
        "allowed_values": {"impact_code": [2, 1, 3]},
    }

    # Get column requirements for the given type
    req_cols = column_requirements.get("required_cols", [])
    allowed_values = column_requirements.get("allowed_values", {})

    # Check that the file contains the required columns
    if not set(req_cols).issubset(df.columns):
        error_msg = (
            f"The file must contain the following columns: {', '.join(req_cols)}"
        )
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    # Check that all values are integers
    for col in df.columns:
        if col in req_cols:
            if not pd.api.types.is_integer_dtype(df[col]):
                error_msg = f"The {col} column must contain only integer values."
                text_field_msg.error_messages = error_msg
                raise ValueError(error_msg)

    # Check that there are no values outside the allowed values in the column requirements
    for col, allowed_vals in allowed_values.items():
        if not set(df[col].unique()).issubset(allowed_vals):
            join_vals = ", ".join([str(val) for val in allowed_vals])
            error_msg = (
                f"The {col} column must contain only the following values: {join_vals}"
            )
            text_field_msg.error_messages = error_msg
            raise ValueError(error_msg)

    if len(df) != len(df.drop_duplicates(subset=["from_code", "to_code"])):
        error_msg = f"The from_code and to_code columns must not have repeated values."
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    # If all good, set the transition code
    df = set_transition_code(df)

    # Save and replace the file
    df.to_csv(file_, index=False)

    return file_


def validate_target_class_file(file_, text_field_msg):
    """Validate the target classification file.

    The target classification file is a csv file with the following columns:

    - lc_class: The land cover class code
    - desc: The land cover class description or display name
    - color: The color to use for the land cover class
    """

    df = read_file(file_, text_field_msg)

    # Define column requirements
    req_cols = ["lc_class", "desc", "color"]

    # Check that the file contains the required columns
    if not set(req_cols).issubset(df.columns):
        error_msg = (
            f"The file must contain the following columns: {', '.join(req_cols)}"
        )
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    # Check that the lc_class column contains only integer values
    if not pd.api.types.is_integer_dtype(df["lc_class"]):
        error_msg = f"The lc_class column must contain only integer values."
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    # Check that the lc_class column doesn't have repeated values.
    if len(df) != len(df.drop_duplicates(subset=["lc_class"])):
        error_msg = f"The lc_class column must not have repeated values."
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    # Check that the color column contains only string values
    if not pd.api.types.is_string_dtype(df["color"]):
        error_msg = f"The color column must contain only string values."
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    # Check that the color column doesn't have repeated values.
    if len(df) != len(df.drop_duplicates(subset=["color"])):
        error_msg = f"The color column must not have repeated values."
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    return file_


def validate_remapping_table(file_, text_field_msg):
    """Validate the remapping table file that is used to reclassify the input asset"""

    df = read_file(file_, text_field_msg).fillna(NO_VALUE)

    column_requirements = {
        "required_cols": MATRIX_NAMES,
        "int_cols": ["from_code", "to_code"],
    }

    # Get column requirements for the given type
    req_cols = column_requirements.get("required_cols", [])

    # Check that the file contains the required columns
    if not set(req_cols).issubset(df.columns):
        error_msg = (
            f"The file must contain the following columns: {', '.join(req_cols)}"
        )
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    # Check that all values are integers
    for col in df.columns:
        if col in req_cols:
            if not pd.api.types.is_integer_dtype(df[col]):
                error_msg = f"The {col} column must contain only integer values."
                text_field_msg.error_messages = error_msg
                raise ValueError(error_msg)

    if len(df) != len(df.drop_duplicates(subset=["from_code", "to_code"])):
        error_msg = f"The from_code and to_code columns must not have repeated values."
        text_field_msg.error_messages = error_msg
        raise ValueError(error_msg)

    return file_


def validate_calc_params(calc_a: bool, calc_b: bool, sub_a_year, sub_b_year, sub_b_val):
    if calc_a:
        if not any([calc_a, calc_b]):
            raise Exception(cm.calculation.error.no_subind)

        else:
            if all([not sub_a_year, not sub_b_year]):
                raise Exception(cm.calculation.error.no_years)

        # Check that all subindicator A have

        if not sub_a_year:
            raise Exception("Subindicator A has no years selected")

        else:
            for idx, year in sub_a_year.items():
                if not year.get("asset"):
                    raise Exception(f"Item {idx} has no asset selected")
                if not year.get("year"):
                    raise Exception(f"Item {idx} has no year selected")

    if calc_b:
        if not sub_b_year:
            raise Exception("Subindicator B has no years selected")

        if sub_b_val:
            if sub_b_val.errors:
                raise Exception("Subindicator B has errors")

    if not any([calc_a, calc_b]):
        raise Exception("Please select at least one subindicator")
