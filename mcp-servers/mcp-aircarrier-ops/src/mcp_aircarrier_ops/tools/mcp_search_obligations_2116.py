"""Search USAspending prime transactions on either CVN-79 prime contract.

N00024-09-C-2116 (construction preparation) and N00024-15-C-2114 (detail design
and construction). The module keeps its original name; the tool was
carrier_search_obligations_2116 until round 2 of the delegation evaluation
found three questions on the second contract with no tool to answer them.

Source: obligations_2116 and obligations_2114 (uc_table).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from mcp_aircarrier_ops.data import sources
from mcp_aircarrier_ops.data.warehouse import (
    WarehouseError,
    column,
    qualified,
    run_query,
)
from mcp_aircarrier_ops.models import ContractValue, DetailValue, OrderValue

TABLE = qualified(
    sources.OBLIGATIONS_2116_CATALOG,
    sources.OBLIGATIONS_2116_SCHEMA,
    sources.OBLIGATIONS_2116_TABLE,
)
TABLE_2114 = qualified(
    sources.OBLIGATIONS_2114_CATALOG,
    sources.OBLIGATIONS_2114_SCHEMA,
    sources.OBLIGATIONS_2114_TABLE,
)
TABLES = {
    ContractValue.CONSTRUCTION_PREPARATION: TABLE,
    ContractValue.DETAIL_DESIGN_AND_CONSTRUCTION: TABLE_2114,
}
COLUMNS = sources.OBLIGATIONS_2116_COLUMNS
AS_OF = sources.OBLIGATIONS_2116_AS_OF

TOOL_NAME = "carrier_search_obligations"

# detail=summary returns these instead of all ~300 USAspending columns
# (12.9 KB per row measured 2026-11-18). Enough to identify the action, its
# obligation, what it bought and where to verify it.
SUMMARY_FIELDS = [
    "contract_transaction_unique_key",
    "award_id_piid",
    "modification_number",
    "action_date",
    "action_date_fiscal_year",
    "federal_action_obligation",
    "total_dollars_obligated",
    "transaction_description",
    "funding_office_name",
    "product_or_service_code_description",
    "recipient_name",
    "usaspending_permalink",
    "_source_locator",
]


def register(mcp: FastMCP) -> None:
    """Register the carrier_search_obligations tool with the MCP server."""

    @mcp.tool(
        name=TOOL_NAME,
        annotations={
            "title": (
                "Search contract actions on the CVN-79 prime contracts "
                "(N00024-09-C-2116, N00024-15-C-2114)"
            ),
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def carrier_search_obligations(
        contract: Annotated[
            ContractValue,
            Field(
                description=(
                    "Which prime contract: N00024-09-C-2116 is construction "
                    "preparation; N00024-15-C-2114 is the Kennedy's detail "
                    "design and construction (DD&C) contract."
                ),
            ),
        ],
        query: Annotated[
            str,
            Field(
                description=(
                    "Keywords to match in descriptions, offices, recipient, PIID or "
                    "modification number (substring, not semantic). Leave empty to "
                    "list actions by the filters alone."
                ),
                max_length=200,
            ),
        ] = "",
        modification_number: Annotated[
            str,
            Field(
                description=(
                    "Exact modification number: '0' is the original (base) award, "
                    "later actions look like 'P00067' or 'A00001'. Empty means any."
                ),
                max_length=12,
            ),
        ] = "",
        fiscal_year: Annotated[
            int,
            Field(
                description=(
                    "Federal fiscal year of the action date, e.g. 2009. 0 means any."
                ),
                ge=0,
                le=2100,
            ),
        ] = 0,
        order: Annotated[
            OrderValue,
            Field(
                description=(
                    "action_date (default) lists actions in date order; "
                    "largest_first puts the largest obligation first, so the "
                    "largest single action is the first row; smallest_first "
                    "puts deobligations first."
                ),
            ),
        ] = OrderValue.ACTION_DATE,
        limit: Annotated[
            int,
            Field(
                description="Maximum rows to return.",
                ge=1,
                le=100,
            ),
        ] = 20,
        offset: Annotated[
            int,
            Field(
                description="Rows to skip from the start.",
                ge=0,
            ),
        ] = 0,
        detail: Annotated[
            DetailValue,
            Field(
                description=(
                    "summary (default) returns 13 key fields per action: keys, "
                    "date, obligation, description, funding office, PSC, recipient "
                    "and the USAspending link. full returns all ~300 columns "
                    "(about 13 KB per row); use it for one action at a time."
                ),
            ),
        ] = DetailValue.SUMMARY,
    ) -> dict[str, Any]:
        """Find contract actions (FPDS/USAspending prime transactions) on a CVN-79
        prime contract, N00024-09-C-2116 (construction preparation) or
        N00024-15-C-2114 (detail design and construction): by keyword, by exact
        modification number (e.g. '0' for the base award) or by fiscal year, in date
        order or largest obligation first. Every order is stable, so offset paging is
        stable.

        One record is one contract action (modification) row; federal_action_obligation
        is that action's obligation. The source refreshes manual re-download from
        USAspending; as_of is the latest action_date in the table at query time.

        Returns: A pagination envelope with total, obligation_total (exact sum of
        federal_action_obligation over every matching action, not just this page),
        count, offset, has_more, next_offset, and the matching records.

        Does not cover: Attribute a budget column to a hull (that is the Attributor's
        job and stays DERIVED); Sum total_dollars_obligated or announced modifications
        as obligations; Write to, promote, or edit any table.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if modification_number.strip():
            clauses.append(column("modification_number", COLUMNS) + " = ?")
            params.append(modification_number.strip().upper())
        if fiscal_year:
            clauses.append(
                "CAST(" + column("action_date_fiscal_year", COLUMNS) + " AS INT) = ?"
            )
            params.append(int(fiscal_year))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        text_columns = [
            "award_id_piid",
            "modification_number",
            "parent_award_agency_name",
            "awarding_agency_name",
            "awarding_sub_agency_name",
            "awarding_office_name",
            "funding_agency_name",
            "funding_sub_agency_name",
            "funding_office_name",
            "foreign_funding_description",
            "sam_exception_description",
            "recipient_name",
            "recipient_name_raw",
            "recipient_doing_business_as_name",
            "recipient_parent_name",
            "recipient_parent_name_raw",
            "recipient_country_name",
            "recipient_city_name",
            "recipient_county_name",
            "recipient_state_name",
            "primary_place_of_performance_country_name",
            "primary_place_of_performance_city_name",
            "primary_place_of_performance_county_name",
            "primary_place_of_performance_state_name",
            "transaction_description",
            "prime_award_base_transaction_description",
            "inherently_governmental_functions_description",
            "product_or_service_code_description",
            "dod_claimant_program_description",
            "naics_description",
            "dod_acquisition_program_description",
            "highly_compensated_officer_1_name",
            "highly_compensated_officer_2_name",
            "highly_compensated_officer_3_name",
            "highly_compensated_officer_4_name",
            "highly_compensated_officer_5_name",
        ]
        try:
            probe = f"%{query.strip().lower()}%"
            likes = [
                f"lower(CAST({column(c, COLUMNS)} AS STRING)) LIKE ?"
                for c in text_columns
            ]
            search_clause = "(" + " OR ".join(likes) + ")"
            if not query.strip():
                joined = where
                bound = list(params)
            elif where:
                joined = f"{where} AND {search_clause}"  # nosemgrep
                bound = list(params) + [probe] * len(text_columns)
            else:
                joined = f" WHERE {search_clause}"  # nosemgrep
                bound = list(params) + [probe] * len(text_columns)
            table = TABLES[contract]
            obligation = column("federal_action_obligation", COLUMNS)
            by_amount = {
                OrderValue.LARGEST_FIRST: f"CAST({obligation} AS DECIMAL(20,2)) DESC, ",
                OrderValue.SMALLEST_FIRST: f"CAST({obligation} AS DECIMAL(20,2)) ASC, ",
            }.get(order, "")
            order_by = (
                " ORDER BY "
                + by_amount
                + ", ".join(
                    column(c, COLUMNS)
                    for c in (
                        "action_date",
                        "modification_number",
                        "transaction_number",
                    )
                )
            )
            action_date = column("action_date", COLUMNS)
            # data_as_of is the latest action in the whole table (not just the
            # filtered rows), so as_of says how fresh the source is.
            totals = run_query(
                "SELECT COUNT(*) AS total, "  # nosemgrep # nosec B608
                f"CAST(SUM(CAST({obligation} AS DECIMAL(20,2))) AS STRING) "
                f"AS obligation_total, "
                f"(SELECT CAST(MAX({action_date}) AS STRING) FROM {table}) "
                f"AS data_as_of FROM {table}{joined}",
                bound,
            )
            total = int(totals[0]["total"]) if totals else 0
            # Exact decimal string over every matching action, not just this
            # page, so an agent never has to add rows up itself.
            obligation_total = totals[0].get("obligation_total") if totals else None
            data_as_of = (totals[0].get("data_as_of") if totals else None) or AS_OF
            select_list = ", ".join(
                column(name, COLUMNS)
                for name in SUMMARY_FIELDS
                if detail is DetailValue.SUMMARY
            ) or ", ".join(
                column(name, COLUMNS)
                for name in [
                    "contract_transaction_unique_key",
                    "contract_award_unique_key",
                    "award_id_piid",
                    "modification_number",
                    "transaction_number",
                    "parent_award_agency_id",
                    "parent_award_agency_name",
                    "parent_award_id_piid",
                    "parent_award_modification_number",
                    "federal_action_obligation",
                    "total_dollars_obligated",
                    "total_outlayed_amount_for_overall_award",
                    "base_and_exercised_options_value",
                    "current_total_value_of_award",
                    "base_and_all_options_value",
                    "potential_total_value_of_award",
                    "disaster_emergency_fund_codes_for_overall_award",
                    "outlayed_amount_from_covid_19_supplementals_for_overall_award",
                    "obligated_amount_from_covid_19_supplementals_for_overall_award",
                    "outlayed_amount_from_iija_supplemental_for_overall_award",
                    "obligated_amount_from_iija_supplemental_for_overall_award",
                    "action_date",
                    "action_date_fiscal_year",
                    "period_of_performance_start_date",
                    "period_of_performance_current_end_date",
                    "period_of_performance_potential_end_date",
                    "ordering_period_end_date",
                    "solicitation_date",
                    "awarding_agency_code",
                    "awarding_agency_name",
                    "awarding_sub_agency_code",
                    "awarding_sub_agency_name",
                    "awarding_office_code",
                    "awarding_office_name",
                    "funding_agency_code",
                    "funding_agency_name",
                    "funding_sub_agency_code",
                    "funding_sub_agency_name",
                    "funding_office_code",
                    "funding_office_name",
                    "treasury_accounts_funding_this_award",
                    "federal_accounts_funding_this_award",
                    "object_classes_funding_this_award",
                    "program_activities_funding_this_award",
                    "foreign_funding",
                    "foreign_funding_description",
                    "sam_exception",
                    "sam_exception_description",
                    "recipient_uei",
                    "recipient_duns",
                    "recipient_name",
                    "recipient_name_raw",
                    "recipient_doing_business_as_name",
                    "cage_code",
                    "recipient_parent_uei",
                    "recipient_parent_duns",
                    "recipient_parent_name",
                    "recipient_parent_name_raw",
                    "recipient_country_code",
                    "recipient_country_name",
                    "recipient_address_line_1",
                    "recipient_address_line_2",
                    "recipient_city_name",
                    "prime_award_transaction_recipient_county_fips_code",
                    "recipient_county_name",
                    "prime_award_transaction_recipient_state_fips_code",
                    "recipient_state_code",
                    "recipient_state_name",
                    "recipient_zip_4_code",
                    "prime_award_transaction_recipient_cd_original",
                    "prime_award_transaction_recipient_cd_current",
                    "recipient_fax_number",
                    "primary_place_of_performance_country_code",
                    "primary_place_of_performance_country_name",
                    "primary_place_of_performance_city_name",
                    "prime_award_transaction_place_of_performance_county_fips_code",
                    "primary_place_of_performance_county_name",
                    "prime_award_transaction_place_of_performance_state_fips_code",
                    "primary_place_of_performance_state_code",
                    "primary_place_of_performance_state_name",
                    "primary_place_of_performance_zip_4",
                    "prime_award_transaction_place_of_performance_cd_original",
                    "prime_award_transaction_place_of_performance_cd_current",
                    "award_or_idv_flag",
                    "award_type_code",
                    "award_type",
                    "idv_type_code",
                    "idv_type",
                    "multiple_or_single_award_idv_code",
                    "multiple_or_single_award_idv",
                    "type_of_idc_code",
                    "type_of_idc",
                    "type_of_contract_pricing_code",
                    "type_of_contract_pricing",
                    "transaction_description",
                    "prime_award_base_transaction_description",
                    "action_type_code",
                    "action_type",
                    "solicitation_identifier",
                    "number_of_actions",
                    "inherently_governmental_functions",
                    "inherently_governmental_functions_description",
                    "product_or_service_code",
                    "product_or_service_code_description",
                    "contract_bundling_code",
                    "contract_bundling",
                    "dod_claimant_program_code",
                    "dod_claimant_program_description",
                    "naics_code",
                    "naics_description",
                    "recovered_materials_sustainability_code",
                    "recovered_materials_sustainability",
                    "domestic_or_foreign_entity_code",
                    "domestic_or_foreign_entity",
                    "dod_acquisition_program_code",
                    "dod_acquisition_program_description",
                    "information_technology_commercial_item_category_code",
                    "information_technology_commercial_item_category",
                    "epa_designated_product_code",
                    "epa_designated_product",
                    "country_of_product_or_service_origin_code",
                    "country_of_product_or_service_origin",
                    "place_of_manufacture_code",
                    "place_of_manufacture",
                    "subcontracting_plan_code",
                    "subcontracting_plan",
                    "extent_competed_code",
                    "extent_competed",
                    "solicitation_procedures_code",
                    "solicitation_procedures",
                    "type_of_set_aside_code",
                    "type_of_set_aside",
                    "evaluated_preference_code",
                    "evaluated_preference",
                    "research_code",
                    "research",
                    "fair_opportunity_limited_sources_code",
                    "fair_opportunity_limited_sources",
                    "other_than_full_and_open_competition_code",
                    "other_than_full_and_open_competition",
                    "number_of_offers_received",
                    "commercial_item_acquisition_procedures_code",
                    "commercial_item_acquisition_procedures",
                    "small_business_competitiveness_demonstration_program",
                    "simplified_procedures_for_certain_commercial_items_code",
                    "simplified_procedures_for_certain_commercial_items",
                    "a76_fair_act_action_code",
                    "a76_fair_act_action",
                    "fed_biz_opps_code",
                    "fed_biz_opps",
                    "local_area_set_aside_code",
                    "local_area_set_aside",
                    "price_evaluation_adjustment_preference_percent_difference",
                    "clinger_cohen_act_planning_code",
                    "clinger_cohen_act_planning",
                    "materials_supplies_articles_equipment_code",
                    "materials_supplies_articles_equipment",
                    "labor_standards_code",
                    "labor_standards",
                    "construction_wage_rate_requirements_code",
                    "construction_wage_rate_requirements",
                    "interagency_contracting_authority_code",
                    "interagency_contracting_authority",
                    "other_statutory_authority",
                    "program_acronym",
                    "parent_award_type_code",
                    "parent_award_type",
                    "parent_award_single_or_multiple_code",
                    "parent_award_single_or_multiple",
                    "major_program",
                    "national_interest_action_code",
                    "national_interest_action",
                    "cost_or_pricing_data_code",
                    "cost_or_pricing_data",
                    "cost_accounting_standards_clause_code",
                    "cost_accounting_standards_clause",
                    "government_furnished_property_code",
                    "government_furnished_property",
                    "sea_transportation_code",
                    "sea_transportation",
                    "undefinitized_action_code",
                    "undefinitized_action",
                    "consolidated_contract_code",
                    "consolidated_contract",
                    "performance_based_service_acquisition_code",
                    "performance_based_service_acquisition",
                    "multi_year_contract_code",
                    "multi_year_contract",
                    "contract_financing_code",
                    "contract_financing",
                    "purchase_card_as_payment_method_code",
                    "purchase_card_as_payment_method",
                    "contingency_humanitarian_or_peacekeeping_operation_code",
                    "contingency_humanitarian_or_peacekeeping_operation",
                    "alaskan_native_corporation_owned_firm",
                    "american_indian_owned_business",
                    "indian_tribe_federally_recognized",
                    "native_hawaiian_organization_owned_firm",
                    "tribally_owned_firm",
                    "veteran_owned_business",
                    "service_disabled_veteran_owned_business",
                    "woman_owned_business",
                    "women_owned_small_business",
                    "economically_disadvantaged_women_owned_small_business",
                    "joint_venture_women_owned_small_business",
                    "joint_venture_economic_disadvantaged_women_owned_small_bus",
                    "minority_owned_business",
                    "subcontinent_asian_asian_indian_american_owned_business",
                    "asian_pacific_american_owned_business",
                    "black_american_owned_business",
                    "hispanic_american_owned_business",
                    "native_american_owned_business",
                    "other_minority_owned_business",
                    "contracting_officers_determination_of_business_size",
                    "contracting_officers_determination_of_business_size_code",
                    "emerging_small_business",
                    "community_developed_corporation_owned_firm",
                    "labor_surplus_area_firm",
                    "us_federal_government",
                    "federally_funded_research_and_development_corp",
                    "federal_agency",
                    "us_state_government",
                    "us_local_government",
                    "city_local_government",
                    "county_local_government",
                    "inter_municipal_local_government",
                    "local_government_owned",
                    "municipality_local_government",
                    "school_district_local_government",
                    "township_local_government",
                    "us_tribal_government",
                    "foreign_government",
                    "organizational_type",
                    "corporate_entity_not_tax_exempt",
                    "corporate_entity_tax_exempt",
                    "partnership_or_limited_liability_partnership",
                    "sole_proprietorship",
                    "small_agricultural_cooperative",
                    "international_organization",
                    "us_government_entity",
                    "community_development_corporation",
                    "domestic_shelter",
                    "educational_institution",
                    "foundation",
                    "hospital_flag",
                    "manufacturer_of_goods",
                    "veterinary_hospital",
                    "hispanic_servicing_institution",
                    "receives_contracts",
                    "receives_financial_assistance",
                    "receives_contracts_and_financial_assistance",
                    "airport_authority",
                    "council_of_governments",
                    "housing_authorities_public_tribal",
                    "interstate_entity",
                    "planning_commission",
                    "port_authority",
                    "transit_authority",
                    "subchapter_scorporation",
                    "limited_liability_corporation",
                    "foreign_owned",
                    "for_profit_organization",
                    "nonprofit_organization",
                    "other_not_for_profit_organization",
                    "the_ability_one_program",
                    "private_university_or_college",
                    "state_controlled_institution_of_higher_learning",
                    "c_1862_land_grant_college",
                    "c_1890_land_grant_college",
                    "c_1994_land_grant_college",
                    "minority_institution",
                    "historically_black_college",
                    "tribal_college",
                    "alaskan_native_servicing_institution",
                    "native_hawaiian_servicing_institution",
                    "school_of_forestry",
                    "veterinary_college",
                    "dot_certified_disadvantage",
                    "self_certified_small_disadvantaged_business",
                    "small_disadvantaged_business",
                    "c8a_program_participant",
                    "historically_underutilized_business_zone_hubzone_firm",
                    "sba_certified_8a_joint_venture",
                    "highly_compensated_officer_1_name",
                    "highly_compensated_officer_1_amount",
                    "highly_compensated_officer_2_name",
                    "highly_compensated_officer_2_amount",
                    "highly_compensated_officer_3_name",
                    "highly_compensated_officer_3_amount",
                    "highly_compensated_officer_4_name",
                    "highly_compensated_officer_4_amount",
                    "highly_compensated_officer_5_name",
                    "highly_compensated_officer_5_amount",
                    "usaspending_permalink",
                    "initial_report_date",
                    "last_modified_date",
                    "_artifact_id",
                    "_row_num",
                    "_row_sha",
                    "_source_locator",
                ]
            )
            rows = run_query(
                f"SELECT {select_list} FROM {table}{joined}{order_by} "  # nosemgrep # nosec B608
                "LIMIT ? OFFSET ?",
                bound + [limit, offset],
            )
        except (ValueError, WarehouseError) as error:
            return {
                "error": str(error),
                "hint": "Try a shorter query, or drop a filter.",
            }
        next_offset = offset + len(rows)
        return {
            "contract": contract.value,
            "order": order.value,
            "as_of": data_as_of,
            "total": total,
            "obligation_total": obligation_total,
            "obligation_total_note": (
                "Sum of federal_action_obligation over all matching actions "
                "(every page), exact to the cent."
            ),
            "count": len(rows),
            "offset": offset,
            "has_more": next_offset < total,
            "next_offset": next_offset if next_offset < total else None,
            "items": rows,
            "detail": detail.value,
            **(
                {"fields_searched": text_columns}
                if detail is DetailValue.FULL
                else {
                    "fields_note": (
                        "Summary fields only; pass detail='full' for every column."
                    )
                }
            ),
        }
