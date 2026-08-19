from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import (
    BranchPythonOperator,
    PythonOperator,
)


AVAILABLE_TOPPINGS = {
    "cheese",
    "mushroom",
    "olives",
}


def receive_order(**context):
    """Receive the order and store its ID in XCom."""
    order_id = "PIZZA-1001"

    context["ti"].xcom_push(
        key="order_id",
        value=order_id,
    )

    context["ti"].log.info(
        "Order received successfully. Order ID: %s",
        order_id,
    )


def validate_order(**context):
    """Validate that the order ID was received correctly."""
    order_id = context["ti"].xcom_pull(
        task_ids="receive_order",
        key="order_id",
    )

    if not order_id:
        context["ti"].log.error(
            "Order validation failed because the order ID is missing."
        )
        raise ValueError("Order ID is missing.")

    context["ti"].log.info(
        "Order %s passed validation.",
        order_id,
    )


def check_ingredients(**context):
    """
    Check whether every requested topping is available.

    If all toppings are available, continue to add_toppings.

    If any topping is unavailable, branch to cancel_order.
    Airflow will automatically skip the pizza-production tasks
    that belong to the other branch.
    """
    order_id = context["ti"].xcom_pull(
        task_ids="receive_order",
        key="order_id",
    )

   
    requested_toppings = context["dag_run"].conf.get(
        "requested_toppings",
        ["cheese", "mushroom", "jalapeno"],
    )

    unavailable_toppings = [
        topping
        for topping in requested_toppings
        if topping not in AVAILABLE_TOPPINGS
    ]

    context["ti"].xcom_push(
        key="requested_toppings",
        value=requested_toppings,
    )

    context["ti"].xcom_push(
        key="unavailable_toppings",
        value=unavailable_toppings,
    )

    context["ti"].log.info(
        "Checking ingredients for order %s.",
        order_id,
    )

    context["ti"].log.info(
        "Requested toppings: %s",
        requested_toppings,
    )

    if unavailable_toppings:
        context["ti"].log.warning(
            "Order %s cannot be prepared because "
            "these toppings are unavailable: %s",
            order_id,
            unavailable_toppings,
        )

        context["ti"].log.warning(
            "Branching to cancel_order. "
            "Pizza production will not continue.",
        )

        return "cancel_order"

    context["ti"].log.info(
        "All requested toppings are available for order %s.",
        order_id,
    )

    context["ti"].log.info(
        "Branching to add_toppings.",
    )

    return "add_toppings"


def add_toppings(**context):
    """Add the requested toppings to the pizza."""
    order_id = context["ti"].xcom_pull(
        task_ids="receive_order",
        key="order_id",
    )

    requested_toppings = context["ti"].xcom_pull(
        task_ids="check_ingredients",
        key="requested_toppings",
    )

    context["ti"].log.info(
        "Adding toppings to order %s: %s",
        order_id,
        requested_toppings,
    )

    context["ti"].log.info(
        "All requested toppings were added successfully.",
    )


def quality_check(**context):
    """Perform the final quality inspection."""
    order_id = context["ti"].xcom_pull(
        task_ids="receive_order",
        key="order_id",
    )

    context["ti"].log.info(
        "Starting quality check for order %s.",
        order_id,
    )

    # Simulated quality check for this assignment.
    quality_passed = True

    if quality_passed:
        context["ti"].log.info(
            "Quality check passed for order %s.",
            order_id,
        )
    else:
        context["ti"].log.critical(
            "Quality check failed for order %s. "
            "The pizza must not be dispatched.",
            order_id,
        )
        raise ValueError("Pizza failed quality check.")


def cancel_order(**context):
    """Cancel an order when a requested topping is unavailable."""
    order_id = context["ti"].xcom_pull(
        task_ids="receive_order",
        key="order_id",
    )

    unavailable_toppings = context["ti"].xcom_pull(
        task_ids="check_ingredients",
        key="unavailable_toppings",
    )

    context["ti"].log.warning(
        "Order %s has been canceled.",
        order_id,
    )

    context["ti"].log.warning(
        "Unavailable toppings: %s",
        unavailable_toppings,
    )

    context["ti"].log.info(
        "No pizza was baked or dispatched for order %s.",
        order_id,
    )


with DAG(
    dag_id="pizza_delivery_pipeline",
    start_date=datetime(2026, 8, 19),
    schedule="30 12,19 * * *",
    catchup=False,
    tags=["pizza", "delivery", "assignment"],
) as dag:

    receive_order_task = PythonOperator(
        task_id="receive_order",
        python_callable=receive_order,
    )

    validate_order_task = PythonOperator(
        task_id="validate_order",
        python_callable=validate_order,
    )

    check_ingredients_task = BranchPythonOperator(
        task_id="check_ingredients",
        python_callable=check_ingredients,
    )

    add_toppings_task = PythonOperator(
        task_id="add_toppings",
        python_callable=add_toppings,
    )

    bake_pizza_task = BashOperator(
        task_id="bake_pizza",
        bash_command=(
            'echo "Oven is preheating..." && '
            'sleep 2 && '
            'echo "Pizza is baking..." && '
            'sleep 3 && '
            'echo "Pizza baking completed successfully."'
        ),
    )

    quality_check_task = PythonOperator(
        task_id="quality_check",
        python_callable=quality_check,
    )

    dispatch_order_task = BashOperator(
        task_id="dispatch_order",
        bash_command=(
            'echo "Preparing pizza for delivery..." && '
            'sleep 2 && '
            'echo "Delivery driver assigned." && '
            'sleep 2 && '
            'echo "Pizza dispatched successfully."'
        ),
    )

    cancel_order_task = PythonOperator(
        task_id="cancel_order",
        python_callable=cancel_order,
    )

    receive_order_task >> validate_order_task
    validate_order_task >> check_ingredients_task

    check_ingredients_task >> add_toppings_task
    add_toppings_task >> bake_pizza_task
    bake_pizza_task >> quality_check_task
    quality_check_task >> dispatch_order_task

    check_ingredients_task >> cancel_order_task