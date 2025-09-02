from temporalio import workflow

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order_id: str, address: dict) -> str:
        """
        Parent workflow: ReceiveOrder -> ValidateOrder -> ChargePayment -> ShippingWorkflow.
        For now, it's just an outline.
        """
        # TODO: call activities in sequence
        # TODO: start ShippingWorkflow as child
        return "OrderWorkflow finished"

    # signals
    @workflow.signal
    async def cancel_order(self): ...
    
    @workflow.signal
    async def update_address(self, new_address: dict): ...
