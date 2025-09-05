# 🚀 Arjun's Temporal Workflow Demo

## What is this?
This is an order tracking simulation that runs in your terminal. 

Start an order and track each step from creation to delivery. Think of it like a domino's pizza tracker that runs automatically -- minus the awesome UI.

![dominos](images/dominos.jpg?raw=true "Title")

## Who cares?
Suppose you work at an infusion center and need to prescribe specialty medication to a patient. 

This is what that process looks like:

![priorauth](images/PriorAuthProcess.png?raw=true "Prior Authorization Process")

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



### Usage

The CLI provides an intuitive interface for order management:

![priorauth](images/main_menu.png?raw=true "Prior Authorization Process")

**🛒 Create a New Order**
- Enter order ID and shipping address
- Workflow starts automatically

![startorder](images/startorder.png?raw=true "Create New Order")


**✅ Approve Orders**
- Select from pending orders
- Send approval signal to continue processing

![approveorder](images/approveorder.png?raw=true "Approve Orders")

**📊 View Order Status**
- Real-time status dashboard
- Tracks status and retry information

![vieworder](images/vieworder.png?raw=true "View Order Status")

**🔍 View Audit Logs**
- Complete event timeline
- Failure analysis and retry tracking

![auditlogs](images/auditlogs.png?raw=true "View Audit Logs")

**📍 Update Order Address**
- Change shipping address for pending orders
- Signal-based updates during workflow execution

![updateaddress](images/updateaddress.png?raw=true "Update Order Address")



**❌ Cancel Orders**
- Cancel active orders with confirmation
- Graceful workflow termination

![cancelorder](images/cancelorder.png?raw=true "Cancel Orders")

## 🧪 Testing

For comprehensive testing and evaluation:

📋 **See [eval_tests/README.md](eval_tests/README.md) for detailed testing instructions**

---