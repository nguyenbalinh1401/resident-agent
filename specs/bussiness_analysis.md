# Capstone Project name:

●​  English: Pulse – Intelligent Resident Services & Management System

●​  Vietnamese: Pulse – Hệ thống quản lý và dịch vụ cư dân thông minh

●​ Abbreviation: SP26SE129

## Context:

While residents enjoy high-tech amenities within their units, the interaction with Building Management remains low-tech. The expectation for luxury living involves "Concierge-level" service—instant, personalized, and effortless. Current solutions lack a centralized "brain" to process natural language requests, forcing users to adapt to the software rather than the software adapting to the user.

## Proposed Solutions

Pulse is an Intelligent Resident Services & Management System that replaces traditional forms with a Conversational Interface.

Core AI Agent (Agentic Workflow): The core of the system is a smart chatbot capable of "taking action" via Intent Recognition. It analyzes user requests to determine the correct workflow—such as distinguishing between service complaints and technical failures—and automatically executes necessary actions or routes tickets to the correct department without manual intervention.

Streamlined Core Services: The system provides a comprehensive suite for living management, focusing on five core business flows: AI Incident Management, Payment Gateway, Amenities Booking, Resident Services, and Package Logistics to create a seamless "Smart Community".


## Functional requirement

### Resident (Mobile App - Flutter)​

1. AI ChatBot Service (Agentic Workflow)

Virtual Receptionist: Acts as a 24/7 assistant answering inquiries regarding building policies and services.

Intelligent Action Handler: The AI analyzes user intent to automatically trigger workflows, such as creating maintenance tickets, checking package status, or navigating to payment screens.

Auto-Execution: Automatically extracts key details (e.g., Location, Severity) from the conversation to submit requests without manual form filling.

2. Report a Problem (Feedback Hub)

Incident Reporting: A dedicated channel for submitting complaints or technical issues.

Intent Classification: AI analyzes the report content to classify the intent (e.g., "Service Attitude" vs. "Technical Failure") and routes it to the correct department (Admin or Technical Staff).

3. Bills & Payment (Payment Gateway)

Bill Viewing: View monthly management fees and utility bills.
Online Payment: Perform payments via the integrated gateway (e.g., VNPay/Momo integration) and view transaction history.
Amenities & Services

Smart Booking: View availability and book amenities (Swimming Pool, Badminton Court, BBQ) with real-time slot checking.
Service Registration: Submit digital requests for Resident Cards, Parking Cards, or Visitor Registration.

4. Logistics & Notifications

Package Alerts: Receive real-time push notifications when a parcel arrives at the reception.
Notification Center: A centralized hub for ticket status updates and building announcements.

### Administrator (Web Dashboard - Next.js)​

1. Ticket & Incident Management

AI-Filtered Tickets: Manage maintenance tickets that have been automatically classified, prioritized, and filtered by the AI Agent.

Task Assignment: Assign specific tasks to Technical Staff or Security based on the AI's classification and severity level.

2. Amenity & Service Management (Merged from Ops Manager)

Booking Approval: Review, approve, or reject booking requests for restricted facilities.

Facility Scheduling: Manage opening hours and set maintenance blocks for amenities to prevent bookings during repair times.

Service Request Processing: Handle administrative requests such as issuing Access Cards or Resident Registration.

3. Core Data Management

Resident Management: Manage resident profiles, unit ownership, and contact details.

Package Operations: Log incoming deliveries at the reception, which automatically triggers notifications to residents.

4. Payment Monitoring

Billing Status: Monitor billing cycles and view payment statuses (Paid/Unpaid) of units (Note: Strictly monitoring only, excluding complex accounting logic).

5. Technical Staff (Mobile App - Flutter)

Task Management: View assigned maintenance tasks with details (Location, Severity, Description).

Status Update: Update the status of tickets (e.g., "In Progress", "Resolved") which triggers notifications to Residents and Admins.


## ​Non-functional requirement:

Performance: The AI Chatbot response and automated ticket generation must occur within acceptable latency (under 3 seconds) to ensure a smooth user experience.

Real-time: The Admin Dashboard must update instantly via WebSocket (SignalR) when new tickets, booking requests, or high-priority issues are reported, ensuring zero delay in operations.

Accuracy: The AI must correctly classify user intent (e.g., distinguishing between "Service Complaints" vs. "Technical Failures") with a high degree of confidence.

The system utilizes a Modular Monolithic architecture to ensure simplicity in deployment and maintenance, allowing the team to focus on core business features while keeping the codebase structured for future updates.

Security: Implement strict Role-based access control (RBAC) clearly distinguishing permissions between Residents, Administrators, and Technical Staff.

## Main proposal content (including result and product)
### Theory and practice (document)

1. Students should apply the software development process and UML 2.0 in the modeling system.​


2. The documents include User Requirements, Software Requirement Specification, Architecture Design, Detail Design, System Implementation, source code (Github).​


3. Server-side technologies:​
- Server: .NET  (ASP.NET Core Web API)
- Database System: PostgreSQL, Cloudinary
- AI Services:Python langchain, Function calling, fastapi, Openai library, prompt tuning.


4. Client-side technologies:​
- Web Client: Next.js (React Framework)
- Mobile Client: Flutter

### Products
- RESTful APIs + WebSocket APIs.​
- Mobile Application for Residents, Staff (AI Chat, Access, Bills).​
- Web Administration Portal.
- AI Integration Module.​
- PostgreSQL Database + ER diagram.​
