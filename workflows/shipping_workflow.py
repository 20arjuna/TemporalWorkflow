from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta

with workflow.unsafe.imports_passed_through():
    from activities import shipping_activities

@workflow.defn
class ShippingWorkflow:
    @workflow.run
    async def run(self, order_id: str, address: dict) -> str:
        # 1. Prepare package
        prepare_result = await workflow.execute_activity(
            shipping_activities.prepare_package,
            args=[order_id, address],
            schedule_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=10),
        )
        print(f"📦 Package prepared: {prepare_result}")

        # 2. Dispatch carrier
        dispatch_result = await workflow.execute_activity(
            shipping_activities.dispatch_carrier,
            args=[order_id, address],
            schedule_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=10),
        )
        print(f"🚚 Carrier dispatched: {dispatch_result}")
        
        return dispatch_result["status"]
