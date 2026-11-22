"""Coordinates and freshness metadata for every data source.

Generated from the server specification. Edit here rather than in the tools,
so a table move or a refresh change is a one-line edit.
"""

from __future__ import annotations

import os
import re

from mcp_aircarrier_ops.config import settings

# --- Where the stores live. Same variable as the docs and analyst servers:
# AIRCARRIER_STORE_SCHEMA=<catalog>.<schema>, set in app.yaml. A deployed app
# without it stops at start-up; a local run or a test reads this placeholder.
DEFAULT_STORE_SCHEMA = "main.aircarrier"
_PART = r"[A-Za-z_][A-Za-z0-9_]{0,254}"


def store_location(value: str | None = None) -> tuple[str, str]:
    """Split AIRCARRIER_STORE_SCHEMA into (catalog, schema), or fail loudly.

    A bad value stops the server at start-up with a plain message, rather than
    surfacing later as a confusing per-tool identifier error.
    """
    # settings reads the environment and, locally, a .env file.
    raw = (value if value is not None else settings.aircarrier_store_schema).strip()
    if not raw and value is None and os.environ.get("DATABRICKS_APP_PORT"):
        raise ValueError("AIRCARRIER_STORE_SCHEMA is not set. Set it in app.yaml.")
    raw = raw or DEFAULT_STORE_SCHEMA
    match = re.fullmatch(rf"({_PART})\.({_PART})", raw)
    if not match:
        raise ValueError(
            "AIRCARRIER_STORE_SCHEMA must be <catalog>.<schema> using letters, "
            f"digits and underscores; got {raw!r}"
        )
    return match.group(1), match.group(2)


STORE_CATALOG, STORE_SCHEMA = store_location()

# --- exhibit_cells: PDF exhibit table cells
EXHIBIT_CELLS_KIND = "uc_table"
EXHIBIT_CELLS_GRAIN = (
    "one cell of one PDF table on one page; value verbatim, value_num exact "
    "decimal string, with row_header, col_header chain and page legends"
)
EXHIBIT_CELLS_CADENCE = "rebuilt on demand when the corpus changes"
EXHIBIT_CELLS_AS_OF = "2026-11-08"
EXHIBIT_CELLS_CATALOG = STORE_CATALOG
EXHIBIT_CELLS_SCHEMA = STORE_SCHEMA
EXHIBIT_CELLS_TABLE = "aircarrier_pdf_cells"
EXHIBIT_CELLS_COLUMNS = (
    "table_id",
    "artifact_id",
    "page",
    "row_idx",
    "col_idx",
    "value",
    "value_kind",
    "value_num",
    "is_header",
    "row_header",
    "col_header",
    "legends",
    "extractor",
    "built_at",
)

# --- obligations_2116: USAspending prime transactions, N00024-09-C-2116
# (CVN-79 construction prep)
OBLIGATIONS_2116_KIND = "uc_table"
OBLIGATIONS_2116_GRAIN = (
    "one contract action (modification) row; federal_action_obligation is "
    "that action's obligation"
)
OBLIGATIONS_2116_CADENCE = "manual re-download from USAspending"
OBLIGATIONS_2116_AS_OF = "2026-06-10"
OBLIGATIONS_2116_CATALOG = STORE_CATALOG
OBLIGATIONS_2116_SCHEMA = STORE_SCHEMA
OBLIGATIONS_2116_TABLE = "aircarrier_src_2116_contract_transactions"
OBLIGATIONS_2116_COLUMNS = (
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
    "recipient_phone_number",
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
)

# --- obligations_2114: USAspending prime transactions, N00024-15-C-2114
# (CVN-79 detail design and construction). Same USAspending prime transaction
# download, so the same columns. Round 2 (question H02) found no tool for it.
OBLIGATIONS_2114_KIND = "uc_table"
OBLIGATIONS_2114_GRAIN = OBLIGATIONS_2116_GRAIN
OBLIGATIONS_2114_CADENCE = OBLIGATIONS_2116_CADENCE
OBLIGATIONS_2114_AS_OF = "2026-07-20"
OBLIGATIONS_2114_CATALOG = STORE_CATALOG
OBLIGATIONS_2114_SCHEMA = STORE_SCHEMA
OBLIGATIONS_2114_TABLE = "aircarrier_src_2114_contract_transactions"
OBLIGATIONS_2114_COLUMNS = OBLIGATIONS_2116_COLUMNS

# --- variances: the variance register, where public sources disagree
VARIANCES_KIND = "uc_table"
VARIANCES_GRAIN = (
    "one variance (E-1 to E-17): where two public sources disagree, and why"
)
VARIANCES_CADENCE = "published from the front center register on each update"
VARIANCES_AS_OF = "2026-11-19"
VARIANCES_CATALOG = STORE_CATALOG
VARIANCES_SCHEMA = STORE_SCHEMA
VARIANCES_TABLE = "aircarrier_variances"
VARIANCES_COLUMNS = (
    "id",
    "status",
    "flag",
    "title",
    "detail",
    "_source",
    "_published_at",
)

# --- graph_edges: Knowledge graph edges
GRAPH_EDGES_KIND = "uc_table"
GRAPH_EDGES_GRAIN = "one directed edge src -rel-> dst between typed node ids (type:key)"
GRAPH_EDGES_CADENCE = "rebuilt by the Knowledge Graph Build notebook"
GRAPH_EDGES_AS_OF = "2026-11-08"
GRAPH_EDGES_CATALOG = STORE_CATALOG
GRAPH_EDGES_SCHEMA = STORE_SCHEMA
GRAPH_EDGES_TABLE = "aircarrier_kg_edges"
GRAPH_EDGES_COLUMNS = (
    "edge_id",
    "src",
    "rel",
    "dst",
    "rule",
    "evidence_artifact_id",
    "evidence_page",
    "evidence_chunk_id",
    "evidence_text",
    "props",
    "built_at",
)

# --- work_register: Work register
WORK_REGISTER_KIND = "uc_table"
WORK_REGISTER_GRAIN = (
    "one work item (kind + ref_id) with its current state and owner_agent"
)
WORK_REGISTER_CADENCE = "each dispatcher tick"
WORK_REGISTER_AS_OF = "2026-11-08"
WORK_REGISTER_CATALOG = STORE_CATALOG
WORK_REGISTER_SCHEMA = STORE_SCHEMA
WORK_REGISTER_TABLE = "aircarrier_work"
WORK_REGISTER_COLUMNS = (
    "work_id",
    "kind",
    "ref_id",
    "state",
    "owner_agent",
    "claimed_at",
    "exposure_usd_m",
    "attempts",
    "last_error",
    "history",
    "updated_at",
)
