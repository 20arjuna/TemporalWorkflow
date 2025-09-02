from temporalio import workflow

@workflow.defn
class ShippingWorkflow:
    @workflow.run
    async def run(self, order_id: str, address: dict) -> str:
        """
        Child workflow: PreparePackage -> DispatchCarrier.
        """
        # TODO: call shipping activities
        return "ShippingWorkflow finished"
