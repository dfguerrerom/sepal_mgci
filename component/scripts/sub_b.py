from typing import Dict, Optional, Tuple, TYPE_CHECKING

import pandas as pd

import component.parameter.module_parameter as param
import component.scripts as cs

# isort: off
from component.parameter.index_parameters import sub_b_landtype_cols, sub_b_perc_cols

from component.scripts.report_scripts import (
    get_impact,
    get_nature,
    get_belt_desc,
    get_obs_status,
)

if TYPE_CHECKING:
    from component.model.model import MgciModel

BELT_TABLE = pd.read_csv(param.BIOBELTS_DESC)
"pd.Dataframe: bioclimatic belts classes and description"


def get_degraded_area(parsed_df: pd.DataFrame, transition_matrix: str):
    """Return net and gross area of degraded land per belt class"""

    # Prepare df
    df = parsed_df.copy()
    df_type = df.reset_index().loc[0, "category"]

    if df_type == "baseline_transition":
        df["impact"] = df.apply(
            lambda x: get_impact(x, transition_matrix=transition_matrix), axis=1
        )
    elif df_type == "final_degradation":
        df["impact"] = df["transition"]
    else:
        raise ValueError("Invalid df_type")

    # get the degraded area
    degraded = (
        df[df.impact == 1]
        .groupby(["belt_class"])
        .sum(numeric_only=True)
        .reset_index()[["belt_class", "sum"]]
    )
    degraded.rename(columns={"sum": "degraded"}, inplace=True)

    # get the stable area
    stable = (
        df[df.impact == 2]
        .groupby(["belt_class"])
        .sum(numeric_only=True)
        .reset_index()[["belt_class", "sum"]]
    )
    stable.rename(columns={"sum": "stable"}, inplace=True)

    # Get net degraded area per belt class as the sum of degraded minus improved

    improved = (
        df[df.impact == 3]
        .groupby(["belt_class"])
        .sum(numeric_only=True)
        .reset_index()[["belt_class", "sum"]]
    )
    improved.rename(columns={"sum": "improved"}, inplace=True)

    net_degraded = degraded.merge(improved, on="belt_class", how="outer")
    net_degraded["net_degraded"] = net_degraded.degraded - net_degraded.improved

    # Add stable area
    net_degraded = net_degraded.merge(stable, on="belt_class", how="outer")

    # we must be sure that all belt classes are present.
    # if not, we must add them with 0 values
    net_degraded = net_degraded.merge(
        BELT_TABLE[["belt_class"]],
        left_on="belt_class",
        right_on="belt_class",
        how="outer",
    )[["belt_class", "degraded", "stable", "improved", "net_degraded"]]

    return net_degraded


def get_pdma_area(parsed_df, transition_matrix: str):
    """Return net and gross area of degraded land per belt class"""

    degraded = get_degraded_area(parsed_df, transition_matrix=transition_matrix)

    # Add new row for total
    total_row = pd.DataFrame(
        [
            [
                "Total",
                degraded.degraded.sum(),
                degraded.stable.sum(),
                degraded.improved.sum(),
                degraded.degraded.sum() - degraded.improved.sum(),
            ]
        ],
        columns=["belt_class", "degraded", "stable", "improved", "net_degraded"],
    )

    return pd.concat([degraded, total_row])


def get_pdma_pt(parsed_df, transition_matrix: str):
    """Return net and gross area (as percentage) of degraded land per belt class"""

    pdma_area = get_pdma_area(parsed_df, transition_matrix=transition_matrix)

    pdma_area["belt_area"] = pdma_area[["degraded", "stable", "improved"]].sum(axis=1)
    pdma_area["pt_degraded"] = pdma_area["degraded"] / pdma_area["belt_area"] * 100
    pdma_area["pt_net_degraded"] = (
        pdma_area["net_degraded"] / pdma_area["belt_area"] * 100
    )

    return pd.concat([pdma_area]).reset_index()


def get_report(
    parsed_df: pd.DataFrame,
    years: Dict[str, Tuple[int, int]],
    geo_area_name: str,
    ref_area: str,
    source_detail: str,
    transition_matrix: str,
    area: Optional[bool] = False,
) -> pd.DataFrame:

    parsed_df = parsed_df.copy()

    if list(years.keys())[0] == "baseline":
        years = list(years.values())[0]
        time_period = f"{years[1]}"
        time_detail = f"{years[0]}-{years[1]}"

    elif list(years.keys())[0] == "report":
        years = list(years.values())[0]
        time_period = f"{years[1]}"
        time_detail = f"2000-{years[1]}"

    else:
        raise ValueError("Invalid year")

    if area:
        report_df = get_pdma_area(parsed_df, transition_matrix)
        report_df["OBS_VALUE"] = report_df["degraded"]
        report_df["OBS_VALUE_NET"] = report_df["net_degraded"]
        # TODO: determine if we're going to use RSA or not
        report_df["OBS_VALUE_RSA"] = param.TBD
        # TODO: determine if we're going to use RSA or not
        report_df["OBS_VALUE_RSA_NET"] = param.TBD
        report_df["UNIT_MEASURE"] = "KM2"
        report_df["UNIT_MULT"] = param.TBD
        output_cols = sub_b_landtype_cols
    else:
        report_df = get_pdma_pt(parsed_df, transition_matrix)
        report_df["OBS_VALUE"] = report_df["pt_degraded"]
        report_df["OBS_VALUE_NET"] = report_df["pt_net_degraded"]
        report_df["UNIT_MEASURE"] = "PT"
        report_df["UNIT_MULT"] = param.TBD

        output_cols = sub_b_perc_cols

    report_df["Indicator"] = "15.4.2"
    report_df["SeriesID"] = param.TBD
    report_df["SERIES"] = param.TBD
    report_df["SeriesDesc"] = param.TBD
    report_df["REF_AREA"] = ref_area
    report_df["GeoAreaName"] = geo_area_name
    report_df["TIME_PERIOD"] = time_period
    report_df["TIME_DETAIL"] = time_detail
    report_df["SOURCE_DETAIL"] = source_detail
    report_df["COMMENT_OBS"] = "FAO estimate"

    report_df["BIOCLIMATIC_BELT"] = report_df.apply(get_belt_desc, axis=1)

    # round obs_value
    report_df["OBS_VALUE"] = report_df["OBS_VALUE"].round(4)
    report_df["OBS_VALUE_NET"] = report_df["OBS_VALUE_NET"].round(4)

    # Convert DataFrame to object type
    report_df = report_df.astype(object)

    # Now fill NaN values with "NA"
    report_df.fillna("NA", inplace=True)

    # fill zeros with "N/A"
    report_df.replace(0, "NA", inplace=True)

    report_df["NATURE"] = report_df.apply(get_nature, axis=1)
    report_df["OBS_STATUS"] = report_df.apply(get_obs_status, axis=1)

    return report_df[output_cols]


def get_reports(
    parsed_df: pd.DataFrame,
    year_s: Dict[str, Tuple[int, int]],
    geo_area_name,
    ref_area,
    source_detail,
    transition_matrix,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    SubIndB_pdma
    SubIndB_pdma_TransitionType

    Args:
        year_s: either {"baseline": (2000, 2015)} or {"report": (2015, 2018)"

    """

    pdma_perc_report = get_report(
        parsed_df,
        year_s,
        geo_area_name,
        ref_area,
        source_detail,
        transition_matrix,
    )

    pdma_land_type_report = get_report(
        parsed_df,
        year_s,
        geo_area_name,
        ref_area,
        source_detail,
        transition_matrix,
        area=True,
    )

    return pdma_perc_report, pdma_land_type_report
