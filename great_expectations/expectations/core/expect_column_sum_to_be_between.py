from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional, Union

from great_expectations.compatibility.typing_extensions import override
from great_expectations.core.evaluation_parameters import (
    EvaluationParameterDict,  # noqa: TCH001
)
from great_expectations.expectations.expectation import (
    ColumnAggregateExpectation,
    render_evaluation_parameter_string,
)
from great_expectations.render import LegacyRendererType, RenderedStringTemplateContent
from great_expectations.render.renderer.renderer import renderer
from great_expectations.render.renderer_configuration import (
    RendererConfiguration,
    RendererValueType,
)
from great_expectations.render.util import (
    handle_strict_min_max,
    parse_row_condition_string_pandas_engine,
    substitute_none_for_missing,
)

if TYPE_CHECKING:
    from great_expectations.core import (
        ExpectationConfiguration,
        ExpectationValidationResult,
    )
    from great_expectations.execution_engine import ExecutionEngine
    from great_expectations.render.renderer_configuration import AddParamArgs


class ExpectColumnSumToBeBetween(ColumnAggregateExpectation):
    """Expect the column to sum to be between a minimum value and a maximum value.

    expect_column_sum_to_be_between is a \
    [Column Aggregate Expectation](https://docs.greatexpectations.io/docs/guides/expectations/creating_custom_expectations/how_to_create_custom_column_aggregate_expectations).

    Args:
        column (str): \
            The column name
        min_value (comparable type or None): \
            The minimal sum allowed.
        max_value (comparable type or None): \
            The maximal sum allowed.
        strict_min (boolean): \
            If True, the minimal sum must be strictly larger than min_value, default=False
        strict_max (boolean): \
            If True, the maximal sum must be strictly smaller than max_value, default=False

    Other Parameters:
        result_format (str or None): \
            Which output mode to use: BOOLEAN_ONLY, BASIC, COMPLETE, or SUMMARY. \
            For more detail, see [result_format](https://docs.greatexpectations.io/docs/reference/expectations/result_format).
        include_config (boolean): \
            If True, then include the expectation config as part of the result object.
        meta (dict or None): \
            A JSON-serializable dictionary (nesting allowed) that will be included in the output without \
            modification. For more detail, see [meta](https://docs.greatexpectations.io/docs/reference/expectations/standard_arguments/#meta).

    Returns:
        An [ExpectationSuiteValidationResult](https://docs.greatexpectations.io/docs/terms/validation_result)

        Exact fields vary depending on the values passed to result_format, include_config, catch_exceptions, and meta.

    Notes:
        * min_value and max_value are both inclusive unless strict_min or strict_max are set to True.
        * If min_value is None, then max_value is treated as an upper bound
        * If max_value is None, then min_value is treated as a lower bound
        * observed_value field in the result object is customized for this expectation to be a list \
          representing the actual column sum
    """

    min_value: Union[float, EvaluationParameterDict, datetime, None] = None
    max_value: Union[float, EvaluationParameterDict, datetime, None] = None
    strict_min: bool = False
    strict_max: bool = False

    # This dictionary contains metadata for display in the public gallery
    library_metadata = {
        "maturity": "production",
        "tags": ["core expectation", "column aggregate expectation"],
        "contributors": ["@great_expectations"],
        "requirements": [],
        "has_full_test_suite": True,
        "manually_reviewed_code": True,
    }

    # Setting necessary computation metric dependencies and defining kwargs, as well as assigning kwargs default values\
    metric_dependencies = ("column.sum",)
    success_keys = (
        "min_value",
        "strict_min",
        "max_value",
        "strict_max",
    )

    # Default values
    default_kwarg_values = {
        "min_value": None,
        "max_value": None,
        "strict_min": None,
        "strict_max": None,
        "result_format": "BASIC",
    }
    args_keys = (
        "column",
        "min_value",
        "max_value",
        "strict_min",
        "strict_max",
    )

    """ A Column Map Metric Decorator for the Sum"""

    @classmethod
    @override
    def _prescriptive_template(
        cls, renderer_configuration: RendererConfiguration
    ) -> RendererConfiguration:
        add_param_args: AddParamArgs = (
            ("column", RendererValueType.STRING),
            ("min_value", [RendererValueType.NUMBER, RendererValueType.DATETIME]),
            ("max_value", [RendererValueType.NUMBER, RendererValueType.DATETIME]),
            ("strict_min", RendererValueType.BOOLEAN),
            ("strict_max", RendererValueType.BOOLEAN),
        )
        for name, param_type in add_param_args:
            renderer_configuration.add_param(name=name, param_type=param_type)

        params = renderer_configuration.params

        if not params.min_value and not params.max_value:
            template_str = "sum may have any numerical value."
        else:
            at_least_str = "greater than or equal to"
            if params.strict_min:
                at_least_str = cls._get_strict_min_string(
                    renderer_configuration=renderer_configuration
                )
            at_most_str = "less than or equal to"
            if params.strict_max:
                at_most_str = cls._get_strict_max_string(
                    renderer_configuration=renderer_configuration
                )

            if params.min_value and params.max_value:
                template_str = f"sum must be {at_least_str} $min_value and {at_most_str} $max_value."
            elif not params.min_value:
                template_str = f"sum must be {at_most_str} $max_value."
            else:
                template_str = f"sum must be {at_least_str} $min_value."

        if renderer_configuration.include_column_name:
            template_str = f"$column {template_str}"

        renderer_configuration.template_str = template_str

        return renderer_configuration

    @classmethod
    @renderer(renderer_type=LegacyRendererType.PRESCRIPTIVE)
    @render_evaluation_parameter_string
    @override
    def _prescriptive_renderer(
        cls,
        configuration: Optional[ExpectationConfiguration] = None,
        result: Optional[ExpectationValidationResult] = None,
        runtime_configuration: Optional[dict] = None,
        **kwargs,
    ) -> list[RenderedStringTemplateContent]:
        renderer_configuration: RendererConfiguration = RendererConfiguration(
            configuration=configuration,
            result=result,
            runtime_configuration=runtime_configuration,
        )
        params = substitute_none_for_missing(
            renderer_configuration.kwargs,
            [
                "column",
                "min_value",
                "max_value",
                "row_condition",
                "condition_parser",
                "strict_min",
                "strict_max",
            ],
        )

        if (params["min_value"] is None) and (params["max_value"] is None):
            template_str = "sum may have any numerical value."
        else:
            at_least_str, at_most_str = handle_strict_min_max(params)

            if params["min_value"] is not None and params["max_value"] is not None:
                template_str = f"sum must be {at_least_str} $min_value and {at_most_str} $max_value."
            elif params["min_value"] is None:
                template_str = f"sum must be {at_most_str} $max_value."
            elif params["max_value"] is None:
                template_str = f"sum must be {at_least_str} $min_value."

        if renderer_configuration.include_column_name:
            template_str = f"$column {template_str}"

        if params["row_condition"] is not None:
            (
                conditional_template_str,
                conditional_params,
            ) = parse_row_condition_string_pandas_engine(params["row_condition"])
            template_str = f"{conditional_template_str}, then {template_str}"
            params.update(conditional_params)

        return [
            RenderedStringTemplateContent(
                **{  # type: ignore[arg-type]
                    "content_block_type": "string_template",
                    "string_template": {
                        "template": template_str,
                        "params": params,
                        "styling": runtime_configuration.get("styling"),
                    },
                }
            )
        ]

    @override
    def _validate(
        self,
        configuration: ExpectationConfiguration,
        metrics: Dict,
        runtime_configuration: Optional[dict] = None,
        execution_engine: Optional[ExecutionEngine] = None,
    ):
        return self._validate_metric_value_between(
            metric_name="column.sum",
            configuration=configuration,
            metrics=metrics,
            runtime_configuration=runtime_configuration,
            execution_engine=execution_engine,
        )
