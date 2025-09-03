from temporalio import workflow
from datetime import timedelta

with workflow.unsafe.imports_passed_through():
    from activities import order_activities
    from workflows.shipping_workflow import ShippingWorkflow

@workflow.defn
class OrderWorkflow:
    def __init__(self):
        self._approved = False
        self._cancelled = False
        self._address = None

    @workflow.run
    async def run(self, order_id: str, address: dict) -> str:
        self._address = address

                # 1. Receive order
        receive_result = await workflow.execute_activity(
            order_activities.receive_order,
            args=[order_id, address],
            schedule_to_close_timeout=timedelta(seconds=20),
        )
        print(f"👋 Received order: {receive_result}")

        # 2. Validate order
        items = ["test_item_1", "test_item_2"]  # Mock items for validation
        validate_result = await workflow.execute_activity(
            order_activities.validate_order,
            args=[order_id, address, items],
            schedule_to_close_timeout=timedelta(seconds=20),
        )
        print(f"👋 Validated order: {validate_result}")
        if validate_result["status"] != "validated":
            return "ValidationFailed"

        # 3. Manual review (3 minute SLA window)
        try:
            await workflow.wait_condition(
                lambda: self._approved or self._cancelled,
                timeout=timedelta(minutes=3),
            )
        except TimeoutError:
            return "AutoCancelled"
        if self._cancelled:
            return "Cancelled"

        print(f"👋 Approved: {self._approved}")

        # 4. Charge payment
        amount = 99.99
        payment_result = await workflow.execute_activity(
            order_activities.charge_payment,
            args=[order_id, address, amount],
            schedule_to_close_timeout=timedelta(seconds=20),
        )
        if payment_result["status"] not in ["charged", "already_charged"]:
            return "PaymentFailed"
        
        print(f"👋 Payment: {payment_result}")



        # 5. Start shipping (child workflow)
        result = await workflow.execute_child_workflow(
            ShippingWorkflow.run,
            args=[order_id, self._address],
            id=f"ship-{order_id}",
            task_queue="shipping-tq",
        )
        print(f"👋 Shipping started: {result}")
        return result

    # ---- Signals ----
    @workflow.signal
    async def approve(self):
        self._approved = True

    @workflow.signal
    async def cancel_order(self):
        self._cancelled = True

    @workflow.signal
    async def update_address(self, new_address: dict):
        self._address = new_address
