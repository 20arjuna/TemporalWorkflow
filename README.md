# 🚀 Arjun's Temporal Workflow Demo

## ❓ What is this?
This is an order tracking simulation that runs in your terminal. 

Start an order and track each step from creation to delivery. Think of it like a domino's pizza tracker that runs automatically -- minus the awesome UI.

<p align="center">
<img src="images/dominos.png?raw=true" alt="Dominos Pizza Tracker" width="700">
</p>

## 👥 Who cares?
Suppose you work at an infusion center and need to prescribe specialty medication to a patient. 

This is what that process looks like:

<p align="center">
<img src="images/PriorAuthProcess.png?raw=true" alt="Prior Authorization Process" width="700">
</p>

Writing a computer program to track this process is **much harder** than building a simple pizza ordering system. Why?

### The Real-World Challenges
- **Things fail at every step** → Denied claims, response delays, wrong information
- **Your system must be resilient** → Can't crash when something goes wrong
- **Zero tolerance for mistakes** → No double-charging patients because you lost track of state
- **Human intervention required** → Manual reviews and approvals in the workflow

**That's exactly why this matters.** Its a computer program that simulates an order moving from creation to delivery **while gracefully dealing with all these real-world complications.**

## 🎯 How to use it

### Pre-requisites
- Docker Desktop - Must be installed and running
- Python 3.8+ installed

### Quick Start
```bash
git clone https://github.com/20arjuna/TemporalWorkflow.git
cd TemporalWorkflow
./start.sh
```

The program should be up and running in your terminal!

> **💡 Note**: The setup process has been fully automated for the best user experience. If you prefer manual setup or need to troubleshoot, see our [**Manual Setup Guide**](ManualSetup.md).


### Usage

The CLI provides an intuitive interface for order management:

<p align="center">
<img src="images/main_menu.png?raw=true" alt="Main Menu" width="500">
</p>

**🛒 Create a New Order**
- Enter order ID and shipping address
- Workflow starts automatically

<p align="center">
<img src="images/startorder.png?raw=true" alt="Create New Order" width="500">
</p>


**✅ Approve Orders**
- Select from pending orders
- Send approval signal to continue processing

<p align="center">
<img src="images/approveorder.png?raw=true" alt="Approve Orders" width="500">
</p>

**📊 View Order Status**
- Real-time status dashboard
- Tracks status and retry information

<p align="center">
<img src="images/vieworder.png?raw=true" alt="View Order Status" width="500">
</p>

**🔍 View Audit Logs**
- Complete event timeline
- Failure analysis and retry tracking

<p align="center">
<img src="images/auditlogs.png?raw=true" alt="View Audit Logs" width="500">
</p>

**📍 Update Order Address**
- Change shipping address for pending orders
- Signal-based updates during workflow execution

<p align="center">
<img src="images/updateaddress.png?raw=true" alt="Update Order Address" width="500">
</p>



**❌ Cancel Orders**
- Cancel active orders with confirmation
- Graceful workflow termination

<p align="center">
<img src="images/cancelorder.png?raw=true" alt="Cancel Orders" width="500">
</p>

## Testing

For comprehensive testing and evaluation:

**See [eval_tests/README.md](eval_tests/README.md) for detailed testing instructions**

## 🏗️ Technical Architecture

### The Temporal Foundation: Activities, Workflows, Workers

#### 🔧 Activities: The Building Blocks
Activities are individual, stateless functions that do the actual work:

**Order Activities** ([`activities/order_activities.py`](activities/order_activities.py)):
- **[`receive_order`](activities/order_activities.py#L17)**: Persists order to PostgreSQL, logs event
- **[`validate_order`](activities/order_activities.py#L70)**: Business rule validation with DB updates
- **[`charge_payment`](activities/order_activities.py#L135)**: Idempotent payment processing with conflict handling

**Shipping Activities** ([`activities/shipping_activities.py`](activities/shipping_activities.py)):
- **[`prepare_package`](activities/shipping_activities.py#L18)**: Package preparation with retry logic
- **[`dispatch_carrier`](activities/shipping_activities.py#L79)**: Carrier dispatch with DB persistence

#### 📋 Workflows: The Orchestrators
Workflows coordinate activities and maintain state:

**[`OrderWorkflow`](workflows/order_workflow.py#L9)** - The Parent:
```python
# The complete flow (lines 19-73)
receive_order → validate_order → [wait_for_approval] → charge_payment → shipping_workflow
```

**[`ShippingWorkflow`](workflows/shipping_workflow.py#L9)** - The Child:
```python  
# Runs independently (lines 13-28)
prepare_package → dispatch_carrier
```

#### ⚙️ Workers: The Execution Engines
Workers run workflows and activities on specific task queues:

**[Order Worker](workers/order_worker.py)**: 
- **Task Queue**: `"orders-tq"` (line 21)
- **Handles**: `OrderWorkflow` + order activities

**[Shipping Worker](workers/shipping_worker.py)**:
- **Task Queue**: `"shipping-tq"` (line 21) 
- **Handles**: `ShippingWorkflow` + shipping activities

**Why Separate Workers?**: Independent scaling, team ownership, fault isolation

### How They Work Together

```
CLI → Temporal Server → Order Worker (orders-tq) → Activities → Database
                     ↓
                  Shipping Worker (shipping-tq) → Activities → Database
```

1. **CLI** starts `OrderWorkflow` on `orders-tq`
2. **Order Worker** picks up workflow, executes activities sequentially  
3. **Activities** persist state to PostgreSQL after each step
4. **OrderWorkflow** spawns `ShippingWorkflow` as child on `shipping-tq`
5. **Shipping Worker** handles shipping independently

### The Complete Order Flow

#### **Step 1: Order Creation & Persistence**
```python
# workflows/order_workflow.py:20-24
receive_result = await workflow.execute_activity(
    order_activities.receive_order,
    args=[order_id, address],
    schedule_to_close_timeout=timedelta(seconds=20)
)
```

**What Happens**:
- **[`receive_order`](activities/order_activities.py#L29)** creates order record in PostgreSQL
- **[Line 37](activities/order_activities.py#L37)**: Logs `order_received` event for audit trail
- **Idempotency**: If order exists, gracefully handles duplicate (lines 31-34)

#### **Step 2: Business Rule Validation** 
```python
# workflows/order_workflow.py:28-36
validate_result = await workflow.execute_activity(
    order_activities.validate_order,
    args=[order_id, address, items],
    schedule_to_close_timeout=timedelta(seconds=20)
)
```

**What Happens**:
- **[`validate_order`](activities/order_activities.py#L70)** checks business rules
- **Database State**: Updates order to `"validating"` then `"validated"`
- **Failure Handling**: Returns `"ValidationFailed"` if rules fail

#### **Step 3: Manual Review Timer (The Human Gate)**
```python
# workflows/order_workflow.py:39-47
await workflow.wait_condition(
    lambda: self._approved or self._cancelled,
    timeout=timedelta(minutes=3)  # 3-minute SLA
)
```

**Signal Handling**:
- **[`approve()`](workflows/order_workflow.py#L77)**: Sets `self._approved = True`
- **[`cancel_order()`](workflows/order_workflow.py#L81)**: Sets `self._cancelled = True` 
- **[`update_address()`](workflows/order_workflow.py#L85)**: Updates shipping address mid-flight

**Timeout Behavior**: Auto-cancels after 3 minutes if no human action

#### **Step 4: Idempotent Payment Processing**
```python
# workflows/order_workflow.py:53-59
payment_result = await workflow.execute_activity(
    order_activities.charge_payment,
    args=[order_id, address, amount],
    schedule_to_close_timeout=timedelta(seconds=20)
)
```

**The Idempotency Magic** ([`charge_payment`](activities/order_activities.py#L135)):

1. **Generate Unique Payment ID** (line 143):
   ```python
   payment_id = f"{order_id}-payment-{attempt_number}"
   ```

2. **Check if Already Processed** (lines 149-165):
   ```python
   is_processed = await PaymentQueries.is_payment_processed(payment_id)
   if is_processed:
       return {"status": "already_charged", ...}
   ```

3. **Database Conflict Handling** ([`db/queries.py:99-102`](db/queries.py#L99)):
   ```sql
   INSERT INTO payments (payment_id, order_id, status, amount)
   VALUES ($1, $2, $3, $4)
   ON CONFLICT (payment_id) DO NOTHING
   ```

4. **Record AFTER Success** (lines 191-201):
   - Call payment gateway: `await stubs.flaky_call()`
   - Update status ONLY after successful charge
   - Log event for audit trail

**Retry Safety**: Multiple payment attempts with same `payment_id` are safe

#### **Step 5: Child Workflow Spawning**
```python
# workflows/order_workflow.py:66-72
result = await workflow.execute_child_workflow(
    ShippingWorkflow.run,
    args=[order_id, self._address],
    id=f"ship-{order_id}",
    task_queue="shipping-tq"  # Different queue!
)
```

**Why Child Workflows?**:
- **Independent Scaling**: Shipping team can scale `shipping-tq` workers independently
- **Fault Isolation**: Shipping failures don't crash order processing
- **Team Ownership**: Different services, different task queues

#### **Step 6: Shipping Execution**
**[`ShippingWorkflow`](workflows/shipping_workflow.py#L11)** runs on separate worker:

```python
# workflows/shipping_workflow.py:13-28
prepare_result = await workflow.execute_activity(prepare_package, ...)
dispatch_result = await workflow.execute_activity(dispatch_carrier, ...)
```

**Retry Policies** (line 17):
```python
retry_policy=RetryPolicy(maximum_attempts=10)
```

**Database Persistence**: Each shipping activity logs to `events` table

### **15-Second SLA Compliance**
- **Activity Timeouts**: 20 seconds max per activity
- **Manual Review**: 3-minute timeout with fallback
- **Parallel Execution**: Child workflows don't block parent completion
- **Database Writes**: Async, non-blocking persistence

### **Observability & Debugging**
- **[`events`](db/migrations/001_init.sql#L23) Table**: Complete audit trail
- **[`activity_attempts`](db/migrations/002_retry_tracking.sql#L15) Table**: Retry tracking with execution times
- **Real-time Status**: CLI queries live database state
- **Temporal Web UI**: Workflow execution history at `localhost:8233`