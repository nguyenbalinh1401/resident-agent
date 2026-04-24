"""Pulse API Client for interacting with Pulse Backend.

This module provides async HTTP client for Pulse Backend API endpoints.
Handles authentication, billing, bookings, tickets, packages, etc.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class PulseConfig:
    """Configuration for Pulse API client."""
    base_url: str = "http://localhost:8080"
    timeout: float = 30.0
    token: Optional[str] = None


@dataclass
class LoginResponse:
    """Response from login endpoint."""
    user_id: str
    full_name: str
    email: str
    role: str
    token: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LoginResponse":
        return cls(
            user_id=str(data.get("userId", "")),
            full_name=data.get("fullName", ""),
            email=data.get("email", ""),
            role=data.get("role", ""),
            token=data.get("token", "")
        )


@dataclass
class RegisterResponse:
    """Response from register endpoint."""
    user_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegisterResponse":
        return cls(user_id=str(data.get("userId", "")))


class PulseAPIError(Exception):
    """Exception raised for Pulse API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class PulseClient:
    """Async HTTP client for Pulse Backend API.

    Provides methods to interact with all Pulse API endpoints including:
    - Authentication (login, register)
    - User management
    - Billing and payments
    - Facility bookings
    - Maintenance tickets
    - Package tracking
    - Notifications
    """

    def __init__(self, config: Optional[PulseConfig] = None):
        """Initialize Pulse client.

        Args:
            config: Pulse API configuration. Uses defaults if not provided.
        """
        self.config = config or PulseConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "PulseClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers=self._get_headers()
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers including auth if token is set."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    def set_token(self, token: str) -> None:
        """Set JWT token for authenticated requests.

        Args:
            token: JWT token from login response
        """
        self.config.token = token
        if self._client:
            self._client.headers["Authorization"] = f"Bearer {token}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Pulse API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            json_data: JSON body for POST/PUT requests
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            PulseAPIError: If request fails
        """
        if not self._client:
            raise PulseAPIError("Client not initialized. Use async with context manager.")

        try:
            response = await self._client.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params
            )

            if response.status_code >= 400:
                error_detail = {}
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = {"raw": response.text}

                raise PulseAPIError(
                    message=f"API request failed: {response.status_code}",
                    status_code=response.status_code,
                    details=error_detail
                )

            return response.json()

        except httpx.TimeoutException:
            raise PulseAPIError(f"Request timeout for {endpoint}")
        except httpx.RequestError as e:
            raise PulseAPIError(f"Request error: {str(e)}")

    # ==================== Authentication ====================

    async def login(self, email: str, password: str) -> LoginResponse:
        """Login user and get JWT token.

        Args:
            email: User's email
            password: User's password

        Returns:
            LoginResponse with user info and JWT token

        Example:
            async with PulseClient() as client:
                response = await client.login("user@example.com", "password123")
                print(f"Logged in as {response.full_name}")
                print(f"Token: {response.token}")
        """
        logger.info("Logging in user", email=email)

        data = await self._request(
            method="POST",
            endpoint="/api/Users/login",
            json_data={
                "email": email,
                "password": password
            }
        )

        response = LoginResponse.from_dict(data)

        # Auto-set token for subsequent requests
        self.set_token(response.token)

        logger.info("Login successful", user_id=response.user_id, role=response.role)
        return response

    async def register(
        self,
        full_name: str,
        phone_number: str,
        password: str,
        email: Optional[str] = None
    ) -> RegisterResponse:
        """Register new user.

        Args:
            full_name: User's full name
            phone_number: User's phone number (must be unique)
            password: User's password
            email: User's email (optional)

        Returns:
            RegisterResponse with new user ID

        Example:
            async with PulseClient() as client:
                response = await client.register(
                    full_name="Nguyen Van A",
                    phone_number="0901234567",
                    password="SecurePassword123!",
                    email="nguyenvana@example.com"
                )
                print(f"Created user: {response.user_id}")
        """
        logger.info("Registering new user", phone_number=phone_number)

        payload = {
            "fullName": full_name,
            "phoneNumber": phone_number,
            "password": password
        }
        if email:
            payload["email"] = email

        data = await self._request(
            method="POST",
            endpoint="/api/Users/register",
            json_data=payload
        )

        response = RegisterResponse.from_dict(data)
        logger.info("Registration successful", user_id=response.user_id)
        return response

    # ==================== User Management ====================

    async def get_current_user(self) -> Dict[str, Any]:
        """Get current authenticated user's profile.

        Returns:
            User profile data
        """
        return await self._request("GET", "/api/Users/me")

    async def update_profile(self, **kwargs) -> Dict[str, Any]:
        """Update current user's profile.

        Args:
            **kwargs: Profile fields to update (fullName, email, etc.)

        Returns:
            Updated user profile
        """
        return await self._request("PUT", "/api/Users/me", json_data=kwargs)

    # ==================== Bills ====================

    async def get_bills(self, unit_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """Get bills for current user.

        Args:
            unit_id: Filter by unit ID
            status: Filter by status (Unpaid, Paid, Overdue)

        Returns:
            List of bills
        """
        params = {}
        if unit_id:
            params["unitId"] = unit_id
        if status:
            params["status"] = status

        return await self._request("GET", "/api/Bills", params=params)

    async def get_bill(self, bill_id: str) -> Dict[str, Any]:
        """Get bill details by ID.

        Args:
            bill_id: Bill ID

        Returns:
            Bill details including line items
        """
        return await self._request("GET", f"/api/Bills/{bill_id}")

    async def create_bill(
        self, unit_id: str, billing_month: str, due_date: str, details: List[Dict]
    ) -> Dict[str, Any]:
        """Create a monthly bill for a unit (Admin/Staff).

        Args:
            unit_id: ID of the unit
            billing_month: Month of the bill (YYYY-MM-01)
            due_date: Due date (YYYY-MM-DD)
            details: List of fee details (FeeTypeId, Subtotal, etc.)

        Returns:
            ID of the created bill
        """
        payload = {
            "unitId": unit_id,
            "billingMonth": billing_month,
            "dueDate": due_date,
            "details": details
        }
        return await self._request("POST", "/api/Bills", json_data=payload)

    async def get_fee_types(self) -> List[Dict]:
        """Get list of fee types (Management, Electricity, Water, etc.)."""
        return await self._request("GET", "/api/FeeTypes")

    # ==================== Payments ====================

    async def create_payment(
        self,
        bill_id: str,
        amount: float,
        payment_method: str
    ) -> Dict[str, Any]:
        """Create payment for a bill.

        Args:
            bill_id: Bill ID to pay
            amount: Payment amount
            payment_method: Payment method (e.g., "VNPay", "Momo", "BankTransfer")

        Returns:
            Payment details including transaction info
        """
        return await self._request(
            "POST",
            "/api/Payments",
            json_data={
                "billId": bill_id,
                "amount": amount,
                "paymentMethod": payment_method
            }
        )

    # ==================== Tickets (Maintenance/Incidents) ====================

    async def create_ticket(
        self,
        category_id: str,
        description: str,
        unit_id: Optional[str] = None,
        severity: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create maintenance/incident ticket.

        Args:
            category_id: Ticket category ID
            description: Issue description
            unit_id: Related unit ID
            severity: Severity level (Low, Medium, High, Critical)
            images: List of image URLs

        Returns:
            Created ticket details
        """
        payload = {
            "categoryId": category_id,
            "description": description
        }
        if unit_id:
            payload["unitId"] = unit_id
        if severity:
            payload["severity"] = severity
        if images:
            payload["images"] = images

        return await self._request("POST", "/api/Tickets", json_data=payload)

    async def get_tickets(self, status: Optional[str] = None) -> List[Dict]:
        """Get tickets for current user.

        Args:
            status: Filter by status (Pending, InProgress, Resolved, Closed)

        Returns:
            List of tickets
        """
        params = {}
        if status:
            params["status"] = status

        return await self._request("GET", "/api/Tickets", params=params)

    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Get ticket details.

        Args:
            ticket_id: Ticket ID

        Returns:
            Ticket details
        """
        return await self._request("GET", f"/api/Tickets/{ticket_id}")

    async def get_ticket_comments(self, ticket_id: str) -> List[Dict]:
        """Get comments for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of comments
        """
        return await self._request("GET", f"/api/Tickets/{ticket_id}/comments")

    async def add_ticket_comment(self, ticket_id: str, content: str) -> Dict[str, Any]:
        """Add a comment to a ticket.

        Args:
            ticket_id: Ticket ID
            content: Comment content

        Returns:
            Created comment
        """
        return await self._request(
            "POST",
            f"/api/Tickets/{ticket_id}/comments",
            json_data={"content": content},
        )

    # ==================== Packages ====================

    async def get_packages(self, unit_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """Get packages for current user/unit.

        Args:
            unit_id: Filter by unit ID
            status: Filter by status (Arrived, PickedUp)

        Returns:
            List of packages
        """
        params = {}
        if unit_id:
            params["unitId"] = unit_id
        if status:
            params["status"] = status

        return await self._request("GET", "/api/Parcels", params=params)

    async def get_package(self, package_id: str) -> Dict[str, Any]:
        """Get package details.

        Args:
            package_id: Package ID

        Returns:
            Package details
        """
        return await self._request("GET", f"/api/Parcels/{package_id}")

    async def delegate_pickup(
        self, parcel_id: str, delegate_name: str, delegate_phone: str
    ) -> Dict[str, Any]:
        """Delegate parcel pickup to another person.

        Args:
            parcel_id: Parcel ID
            delegate_name: Name of the delegate
            delegate_phone: Phone number of the delegate

        Returns:
            Delegation result
        """
        return await self._request(
            "POST",
            f"/api/Parcels/{parcel_id}/delegate",
            json_data={
                "delegateName": delegate_name,
                "delegatePhone": delegate_phone,
            },
        )

    async def revoke_pickup_delegation(self, parcel_id: str) -> Dict[str, Any]:
        """Revoke parcel pickup delegation.

        Args:
            parcel_id: Parcel ID

        Returns:
            Revocation result
        """
        return await self._request("DELETE", f"/api/Parcels/{parcel_id}/delegate")

    # ==================== Amenities & Bookings ====================

    async def get_amenities(self, category_id: Optional[str] = None) -> List[Dict]:
        """Get available amenities.

        Args:
            category_id: Filter by category ID

        Returns:
            List of amenities
        """
        params = {}
        if category_id:
            params["categoryId"] = category_id

        return await self._request("GET", "/api/Amenities", params=params)

    async def get_amenity(self, amenity_id: str) -> Dict[str, Any]:
        """Get amenity details including availability.

        Args:
            amenity_id: Amenity ID

        Returns:
            Amenity details
        """
        return await self._request("GET", f"/api/Amenities/{amenity_id}")

    async def create_booking(
        self,
        amenity_id: str,
        booking_date: str,
        start_time: str,
        end_time: str
    ) -> Dict[str, Any]:
        """Create amenity booking.

        Args:
            amenity_id: Amenity ID to book
            booking_date: Date in YYYY-MM-DD format
            start_time: Start time in HH:MM format
            end_time: End time in HH:MM format

        Returns:
            Booking details
        """
        return await self._request(
            "POST",
            "/api/Bookings",
            json_data={
                "amenityId": amenity_id,
                "bookingDate": booking_date,
                "startTime": start_time,
                "endTime": end_time
            }
        )

    async def get_bookings(self, status: Optional[str] = None) -> List[Dict]:
        """Get user's bookings.

        Args:
            status: Filter by status (Pending, Confirmed, Cancelled, Completed)

        Returns:
            List of bookings
        """
        params = {}
        if status:
            params["status"] = status

        return await self._request("GET", "/api/Bookings", params=params)

    async def cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Cancel a booking.

        Args:
            booking_id: Booking ID

        Returns:
            Cancellation result
        """
        return await self._request("DELETE", f"/api/Bookings/{booking_id}")

    # ==================== Reference Data ====================

    async def get_ticket_categories(self) -> List[Dict]:
        """Get available ticket/incident categories."""
        return await self._request("GET", "/api/TicketCategories")

    async def get_amenity_categories(self) -> List[Dict]:
        """Get available amenity categories."""
        return await self._request("GET", "/api/AmenityCategories")

    async def get_request_types(self) -> List[Dict]:
        """Get available resident request types."""
        return await self._request("GET", "/api/ResidentRequests/request-types")

    # ==================== Surveys ====================

    async def get_surveys(self) -> List[Dict]:
        """Get available surveys."""
        return await self._request("GET", "/api/Surveys")

    async def submit_survey_answer(
        self, survey_id: str, answers: list
    ) -> Dict[str, Any]:
        """Submit survey answers.

        Args:
            survey_id: Survey ID
            answers: List of answers

        Returns:
            Submission result
        """
        return await self._request(
            "POST",
            "/api/Surveys/answers",
            json_data={"surveyId": survey_id, "answers": answers},
        )

    # ==================== Vehicles ====================
    async def get_my_vehicles(self) -> List[Dict]:
        """Get vehicles registered to the current user."""
        return await self._request("GET", "/api/Vehicles/my")

    async def register_vehicle(
        self, plate_number: str, brand: str, color: str, vehicle_type: str
    ) -> Dict[str, Any]:
        """Create a vehicle registration request.

        Args:
            plate_number: License plate
            brand: Vehicle brand
            color: Vehicle color
            vehicle_type: Type (Car, Motorbike, etc.)

        Returns:
            Created request details
        """
        # We need the request_type_id for 'Vehicle Card' or 'VehicleCard'
        # For simplicity in the agent, we first fetch types to find the ID
        types = await self.get_request_types()
        v_type = next((t for t in types if t["name"] in ["VehicleCard", "Vehicle Card"]), None)
        
        if not v_type:
            raise ValueError("Vehicle registration type not found on server")

        payload = {
            "requestTypeId": v_type["id"],
            "requestDataJson": json.dumps({
                "plateNumber": plate_number,
                "brand": brand,
                "color": color,
                "vehicleType": vehicle_type
            })
        }
        return await self._request("POST", "/api/ResidentRequests", json_data=payload)

    # ==================== Resident Requests ====================

    async def get_resident_requests(
        self, status: Optional[str] = None
    ) -> List[Dict]:
        """Get resident's requests.

        Args:
            status: Filter by status

        Returns:
            List of requests
        """
        params = {}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/ResidentRequests", params=params)

    async def get_resident_request(self, request_id: str) -> Dict[str, Any]:
        """Get resident request detail.

        Args:
            request_id: Request ID

        Returns:
            Request details
        """
        return await self._request("GET", f"/api/ResidentRequests/{request_id}")

    # ==================== Resident Registries (Admin/Waitlist) ====================

    async def get_resident_registries(self, status: Optional[str] = None) -> List[Dict]:
        """Get pre-approved resident registry list (Admin).

        Args:
            status: Filter by Status (Pending/Verified/Rejected)

        Returns:
            List of registry entries
        """
        params = {}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/ResidentRegistries", params=params)

    async def create_resident_registry(
        self, phone_number: str, unit_id: str, full_name: Optional[str] = None
    ) -> str:
        """Create a pre-approved resident registry entry (Admin).

        Args:
            phone_number: Resident's phone number
            unit_id: Unit ID to pre-approve
            full_name: Optional full name

        Returns:
            ID of the created record
        """
        payload = {
            "phoneNumber": phone_number,
            "unitId": unit_id
        }
        if full_name:
            payload["fullName"] = full_name

        return await self._request("POST", "/api/ResidentRegistries", json_data=payload)

    async def update_resident_registry_status(
        self, registry_id: str, status: str
    ) -> Dict[str, Any]:
        """Update resident registry status (Admin: Verified/Rejected).

        Args:
            registry_id: ID of the registry record
            status: New status (Verified, Rejected)

        Returns:
            Update result
        """
        return await self._request(
            "PUT",
            f"/api/ResidentRegistries/{registry_id}/status",
            json_data={"status": status},
        )

    async def request_resident_verification(
        self, unit_id: str, full_name: str, phone_number: str
    ) -> Dict[str, Any]:
        """Request resident verification for an account (User).

        Args:
            unit_id: Target unit ID
            full_name: User's full name
            phone_number: User's phone number

        Returns:
            Created request details
        """
        payload = {
            "unitId": unit_id,
            "fullName": full_name,
            "phoneNumber": phone_number,
        }
        return await self._request("POST", "/api/Users/request-resident", json_data=payload)

    # ==================== Units ====================

    async def get_units(self) -> List[Dict]:
        """Get list of building units."""
        return await self._request("GET", "/api/Units")

    # ==================== Notifications ====================

    async def get_payment_history(
        self, bill_id: Optional[str] = None
    ) -> List[Dict]:
        """Get payment history for current user.

        Args:
            bill_id: Filter by bill ID

        Returns:
            List of payment records
        """
        params = {}
        if bill_id:
            params["billId"] = bill_id
        return await self._request(
            "GET", "/api/v1/resident/payments/history", params=params
        )

    async def get_notifications(self, unread_only: bool = False) -> List[Dict]:
        """Get user notifications.

        Args:
            unread_only: Only return unread notifications

        Returns:
            List of notifications
        """
        params = {"unreadOnly": unread_only} if unread_only else {}
        return await self._request("GET", "/api/Notifications", params=params)

    async def mark_notification_read(self, notification_id: str) -> Dict[str, Any]:
        """Mark notification as read.

        Args:
            notification_id: Notification ID

        Returns:
            Result
        """
        return await self._request("PUT", f"/api/Notifications/{notification_id}/read")

    async def mark_all_notifications_read(self) -> Dict[str, Any]:
        """Mark all notifications as read."""
        return await self._request("PUT", "/api/v1/resident/notifications/read-all")

    async def get_unread_notification_count(self) -> Dict[str, Any]:
        """Get count of unread notifications."""
        return await self._request("GET", "/api/Notifications/unread-count")

    # ==================== Announcements ====================

    async def get_announcements(self) -> List[Dict]:
        """Get building announcements.

        Args:
            limit: Maximum number of announcements

        Returns:
            List of announcements
        """
        return await self._request("GET", "/api/Announcements")

    # ==================== User Roles & Permissions ====================

    async def get_user_roles(self, user_id: str) -> Dict[str, Any]:
        """Get user's roles and permissions.

        This is used by Chat API to determine user capabilities (allowance).

        Args:
            user_id: User identifier

        Returns:
            Dict with roles, permissions, and effectiveCapabilities

        Example:
            async with PulseClient(config) as client:
                roles = await client.get_user_roles("user-123")
                print(roles["effectiveCapabilities"])
        """
        logger.info("fetching_user_roles", user_id=user_id)
        return await self._request("GET", f"/api/UserRoles/{user_id}")

    async def get_actions(self) -> Dict[str, Any]:
        """Get all available action definitions.

        This is used by Chat API for hybrid action generation.

        Returns:
            Dict with categories of actions

        Example:
            async with PulseClient(config) as client:
                actions = await client.get_actions()
                for cat in actions["categories"]:
                    print(f"Category: {cat['name']}")
                    for action in cat["actions"]:
                        print(f"  - {action['label']}")
        """
        logger.info("fetching_actions")
        return await self._request("GET", "/api/Actions")

    async def get_permissions(self) -> List[Dict[str, str]]:
        """Get permissions for current authenticated user.

        This is used by Chat API to filter available tools based on user permissions.

        Returns:
            List of permissions with format [{"resource": str, "action": str}]

        Example:
            async with PulseClient(config) as client:
                await client.login(phone, password)
                permissions = await client.get_permissions()
                # [{"resource": "Bills", "action": "Read"}, ...]
        """
        logger.info("fetching_permissions")
        return await self._request("GET", "/api/Permissions")


# Convenience function for quick usage
async def create_authenticated_client(email: str, password: str, base_url: str = "http://localhost:5000") -> PulseClient:
    """Create and authenticate a Pulse client.

    Args:
        email: User's email
        password: User's password
        base_url: Pulse API base URL

    Returns:
        Authenticated PulseClient instance

    Example:
        async with await create_authenticated_client("user@example.com", "password") as client:
            bills = await client.get_bills()
            print(bills)
    """
    config = PulseConfig(base_url=base_url)
    client = PulseClient(config)
    await client.__aenter__()
    await client.login(email, password)
    return client
