"""Pulse API Client for interacting with Pulse Backend.

This module provides async HTTP client for Pulse Backend API endpoints.
Handles authentication, billing, bookings, tickets, packages, etc.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import base64
import json
import httpx
import structlog
import re

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

    @staticmethod
    def _is_guid(value: Optional[str]) -> bool:
        if not value:
            return False
        return bool(
            re.fullmatch(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                value.strip(),
            )
        )

    async def _resolve_ticket_category_name(self, category_identifier: Optional[str]) -> Optional[str]:
        if not category_identifier:
            return None

        categories = await self.get_ticket_categories()
        normalized_identifier = category_identifier.strip().lower()

        for category in categories:
            category_id = str(category.get("id") or "")
            category_name = str(
                category.get("name")
                or category.get("categoryName")
                or category.get("title")
                or ""
            ).strip()

            if category_id and category_id == category_identifier:
                return category_name or None

            if category_name and category_name.lower() == normalized_identifier:
                return category_name

        if not self._is_guid(category_identifier):
            return category_identifier.strip()

        return None

    async def _get_current_active_unit_id(self) -> Optional[str]:
        """Resolve the current user's active unit ID for resident-only actions."""
        try:
            my_unit = await self._request("GET", "/api/v1/resident/my-unit")
        except PulseAPIError:
            return None

        if isinstance(my_unit, dict):
            unit_id = my_unit.get("unitId") or my_unit.get("id")
            if unit_id:
                return str(unit_id)

        return None

    async def _is_privileged_user(self) -> bool:
        """Best-effort check for admin/staff/manager scopes."""
        try:
            current_user = await self.get_current_user()
        except PulseAPIError:
            return False

        role = str(current_user.get("role") or "").strip().lower()
        return role in {"admin", "staff", "manager"}

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

        endpoint = "/api/Bills" if await self._is_privileged_user() else "/api/v1/resident/bills"
        return await self._request("GET", endpoint, params=params)

    async def get_bill(self, bill_id: str) -> Dict[str, Any]:
        """Get bill details by ID.

        Args:
            bill_id: Bill ID

        Returns:
            Bill details including line items
        """
        endpoint = f"/api/Bills/{bill_id}" if await self._is_privileged_user() else f"/api/v1/resident/bills/{bill_id}"
        return await self._request("GET", endpoint)

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

    async def get_utility_preview(
        self,
        unit_id: str,
        billing_month: str,
    ) -> List[Dict]:
        """Get utility preview rows for a unit and billing month (Admin/Staff).

        Args:
            unit_id: ID of the unit
            billing_month: Billing month in YYYY-MM-01 format

        Returns:
            List of calculated preview rows
        """
        return await self._request(
            "GET",
            "/api/Bills/utility-preview",
            params={
                "unitId": unit_id,
                "billingMonth": billing_month,
            },
        )

    async def notify_bill_residents(self, bill_id: str) -> Dict[str, Any]:
        """Notify residents of a bill (Admin only)."""
        return await self._request("POST", f"/api/Bills/{bill_id}/notify")

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

    async def record_manual_payment(
        self,
        bill_id: str,
        paid_by: str,
        amount_paid: float,
        payment_method: str,
    ) -> Dict[str, Any]:
        """Record a manual counter payment (Admin/Staff)."""
        return await self._request(
            "POST",
            "/api/Payments/manual",
            json_data={
                "billId": bill_id,
                "paidBy": paid_by,
                "amountPaid": amount_paid,
                "paymentMethod": payment_method,
            },
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
        category_name = await self._resolve_ticket_category_name(category_id)
        effective_unit_id = unit_id or await self._get_current_active_unit_id()

        payload = {
            "description": description,
            "imageUrls": images or [],
            "unitId": effective_unit_id,
            "categoryName": category_name,
            "severity": severity,
        }

        return await self._request("POST", "/api/v1/resident/incidents", json_data=payload)

    async def upload_ticket_images_from_attachments(
        self,
        ticket_id: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        image_type: str = "Before",
    ) -> List[str]:
        """Upload inline chat image attachments to an existing ticket.

        Args:
            ticket_id: Created ticket ID
            attachments: Chat attachments carrying base64 image payloads
            image_type: Ticket image type expected by backend

        Returns:
            List of uploaded image URLs from backend
        """
        if not ticket_id or not attachments:
            return []

        image_attachments = []
        for index, att in enumerate(attachments):
            if str(att.get("type") or "").lower() != "image":
                continue
            data = att.get("data")
            mime_type = str(att.get("mime_type") or "image/jpeg")
            if not data:
                continue
            try:
                binary = base64.b64decode(data)
            except Exception:
                logger.warning("ticket_attachment_decode_failed", ticket_id=ticket_id, index=index)
                continue

            extension = ".jpg"
            if "/" in mime_type:
                guessed = mime_type.split("/", 1)[1].strip().lower()
                if guessed in {"jpeg", "jpg", "png", "webp"}:
                    extension = ".jpg" if guessed == "jpeg" else f".{guessed}"

            image_attachments.append(
                (
                    "files",
                    (f"agent-ticket-{index + 1}{extension}", binary, mime_type),
                )
            )

        if not image_attachments:
            return []

        if not self.config.token:
            raise PulseAPIError("Missing auth token for ticket image upload.")

        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.config.token}"}
        async with httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers=headers,
        ) as upload_client:
            response = await upload_client.post(
                f"/api/Tickets/{ticket_id}/images/upload-batch",
                data={"imageType": image_type},
                files=image_attachments,
            )

        if response.status_code >= 400:
            error_detail = {}
            try:
                error_detail = response.json()
            except Exception:
                error_detail = {"raw": response.text}
            raise PulseAPIError(
                message=f"Ticket image upload failed: {response.status_code}",
                status_code=response.status_code,
                details=error_detail,
            )

        payload = response.json()
        if isinstance(payload, dict):
            urls = payload.get("imageUrls")
            if isinstance(urls, list):
                return [str(url) for url in urls]
        return []

    async def get_tickets(
        self,
        status: Optional[str] = None,
        reported_by: Optional[str] = None,
        category_id: Optional[str] = None,
        severity: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict]:
        """Get tickets for current user.

        Args:
            status: Filter by status (Pending, InProgress, Resolved, Closed)
            reported_by: Filter by reporter user ID
            category_id: Filter by category ID
            severity: Filter by severity
            page: Page number
            page_size: Page size

        Returns:
            List of tickets
        """
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if status:
            params["status"] = status
        if reported_by:
            params["reportedBy"] = reported_by
        if category_id:
            params["categoryId"] = category_id
        if severity:
            params["severity"] = severity

        return await self._request("GET", "/api/Tickets", params=params)

    async def get_my_incidents(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict]:
        """Get incidents for the current resident only."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/v1/resident/incidents", params=params)

    async def get_my_incident(self, ticket_id: str) -> Dict[str, Any]:
        """Get a resident-scoped incident detail."""
        return await self._request("GET", f"/api/v1/resident/incidents/{ticket_id}")

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

    async def update_ticket_status(self, ticket_id: str, status: str) -> Dict[str, Any]:
        """Update ticket status (Admin/Staff)."""
        return await self._request(
            "PUT",
            f"/api/Tickets/{ticket_id}/status",
            json_data={"status": status},
        )

    async def update_ticket_severity(self, ticket_id: str, severity: str) -> Dict[str, Any]:
        """Update ticket severity."""
        return await self._request(
            "PUT",
            f"/api/Tickets/{ticket_id}/severity",
            json_data={"severity": severity},
        )

    async def assign_ticket(
        self,
        ticket_id: str,
        assigned_to: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assign a ticket to a staff member (Admin/Staff)."""
        payload: Dict[str, Any] = {
            "assignedTo": assigned_to,
            "notes": notes,
        }
        return await self._request("PUT", f"/api/Tickets/{ticket_id}/assign", json_data=payload)

    async def approve_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Approve a ticket (Admin/Staff)."""
        return await self._request("POST", f"/api/Tickets/{ticket_id}/approve")

    async def reject_ticket(self, ticket_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Reject a ticket (Admin/Staff)."""
        return await self._request(
            "POST",
            f"/api/Tickets/{ticket_id}/reject",
            json_data={"reason": reason},
        )

    async def complete_ticket(self, ticket_id: str, note: Optional[str] = None) -> Dict[str, Any]:
        """Complete a ticket (Admin/Staff)."""
        return await self._request(
            "POST",
            f"/api/Tickets/{ticket_id}/complete",
            json_data={"note": note},
        )

    # ==================== Packages ====================

    async def get_packages(
        self,
        unit_id: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        resident_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict]:
        """Get packages for current user/unit.

        Args:
            unit_id: Filter by unit ID
            status: Filter by status (Arrived, PickedUp)
            owner_id: Filter by parcel owner user ID
            resident_id: Filter by resident ID
            date_from: Filter from datetime
            date_to: Filter to datetime
            page: Page number
            page_size: Page size

        Returns:
            List of packages
        """
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if not owner_id and not resident_id and not await self._is_privileged_user():
            current_user = await self.get_current_user()
            resident_id = str(
                current_user.get("userId")
                or current_user.get("id")
                or ""
            ) or None
        if unit_id:
            params["unitId"] = unit_id
        if status:
            params["status"] = status
        if owner_id:
            params["ownerId"] = owner_id
        if resident_id:
            params["residentId"] = resident_id
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to

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
        self,
        parcel_id: str,
        delegatee_id: str,
    ) -> Dict[str, Any]:
        """Delegate parcel pickup to another person.

        Args:
            parcel_id: Parcel ID
            delegatee_id: User ID of the delegatee

        Returns:
            Delegation result
        """
        return await self._request(
            "POST",
            f"/api/Parcels/{parcel_id}/delegate",
            json_data={"delegateeId": delegatee_id},
        )

    async def revoke_pickup_delegation(self, parcel_id: str) -> Dict[str, Any]:
        """Revoke parcel pickup delegation.

        Args:
            parcel_id: Parcel ID

        Returns:
            Revocation result
        """
        return await self._request("DELETE", f"/api/Parcels/{parcel_id}/delegate")

    async def lookup_delivery_code(self, code: str) -> List[Dict]:
        """Autocomplete resident by delivery code (Admin/Staff)."""
        return await self._request("GET", "/api/Parcels/lookup", params={"code": code})

    async def lookup_parcel_resident(self, unit_id: str, name: str) -> List[Dict]:
        """Lookup resident within a unit for parcel delegation/help."""
        return await self._request(
            "GET",
            "/api/Parcels/resident-lookup",
            params={"unitId": unit_id, "name": name},
        )

    async def generate_pickup_token(self, parcel_id: str) -> Dict[str, Any]:
        """Generate pickup token/QR payload for a parcel (Resident)."""
        return await self._request("GET", f"/api/Parcels/{parcel_id}/pickup-token")

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

        return await self._request("GET", "/api/v1/resident/amenities", params=params)

    async def get_amenity(self, amenity_id: str) -> Dict[str, Any]:
        """Get amenity details including availability.

        Args:
            amenity_id: Amenity ID

        Returns:
            Amenity details
        """
        return await self._request("GET", f"/api/Amenities/{amenity_id}")

    async def create_amenity(
        self,
        category_id: str,
        name: str,
        type: str,
        description: Optional[str] = None,
        capacity: Optional[int] = None,
        require_approval: bool = False,
        max_concurrent_bookings: Optional[int] = None,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        """Create a new amenity (Admin/authorized role)."""
        payload: Dict[str, Any] = {
            "categoryId": category_id,
            "name": name,
            "type": type,
            "requireApproval": require_approval,
            "isActive": is_active,
        }
        if description is not None:
            payload["description"] = description
        if capacity is not None:
            payload["capacity"] = capacity
        if max_concurrent_bookings is not None:
            payload["maxConcurrentBookings"] = max_concurrent_bookings

        return await self._request("POST", "/api/Amenities", json_data=payload)

    async def update_amenity(
        self,
        amenity_id: str,
        category_id: str,
        name: str,
        type: str,
        max_concurrent_bookings: int,
        is_active: bool,
        description: Optional[str] = None,
        capacity: Optional[int] = None,
        require_approval: bool = False,
    ) -> Dict[str, Any]:
        """Update an existing amenity (Admin/authorized role)."""
        payload: Dict[str, Any] = {
            "id": amenity_id,
            "categoryId": category_id,
            "name": name,
            "type": type,
            "maxConcurrentBookings": max_concurrent_bookings,
            "isActive": is_active,
            "requireApproval": require_approval,
        }
        if description is not None:
            payload["description"] = description
        if capacity is not None:
            payload["capacity"] = capacity

        return await self._request("PUT", f"/api/Amenities/{amenity_id}", json_data=payload)

    async def delete_amenity(self, amenity_id: str) -> Dict[str, Any]:
        """Delete an amenity (Admin/authorized role)."""
        return await self._request("DELETE", f"/api/Amenities/{amenity_id}")

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
        if not self._is_guid(amenity_id):
            raise PulseAPIError(
                "Amenity ID is invalid for the current Pulse system. Fetch amenities again before booking.",
                status_code=400,
                details={"amenityId": amenity_id},
            )

        return await self._request(
            "POST",
            "/api/v1/resident/bookings",
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

        return await self._request("GET", "/api/v1/resident/bookings", params=params)

    async def get_bookings_queue(
        self,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        amenity_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get operational booking queue for admin/staff scopes."""
        params: Dict[str, Any] = {}
        if status:
            params["status"] = status
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if amenity_id:
            params["amenityId"] = amenity_id
        if user_id:
            params["userId"] = user_id
        return await self._request("GET", "/api/Bookings", params=params)

    async def approve_booking(self, booking_id: str) -> Dict[str, Any]:
        """Approve a pending booking."""
        return await self._request("POST", f"/api/Bookings/{booking_id}/approve")

    async def reject_booking(self, booking_id: str, reason: str) -> Dict[str, Any]:
        """Reject a pending booking with a reason."""
        return await self._request(
            "POST",
            f"/api/Bookings/{booking_id}/reject",
            json_data={"reason": reason},
        )

    async def cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """Cancel a booking.

        Args:
            booking_id: Booking ID

        Returns:
            Cancellation result
        """
        return await self._request(
            "PUT",
            f"/api/v1/resident/bookings/{booking_id}/cancel",
            json_data={"reason": "Cancelled by Pulse AI assistant"},
        )

    # ==================== Reference Data ====================

    async def get_ticket_categories(self) -> List[Dict]:
        """Get available ticket/incident categories."""
        return await self._request("GET", "/api/TicketCategories")

    async def get_amenity_categories(self) -> List[Dict]:
        """Get available amenity categories."""
        return await self._request("GET", "/api/AmenityCategories")

    async def get_request_types(self) -> List[Dict]:
        """Get available resident request types."""
        return await self._request("GET", "/api/ResidentRequests/types")

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

    async def create_resident_request(
        self,
        request_type_id: str,
        request_data_json: str,
        requester_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a resident request."""
        return await self._request(
            "POST",
            "/api/ResidentRequests",
            json_data={
                "requesterId": requester_id,
                "requestTypeId": request_type_id,
                "requestDataJson": request_data_json,
            },
        )

    async def approve_resident_request(
        self,
        request_id: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a resident request (Admin/Manager)."""
        return await self._request(
            "POST",
            f"/api/ResidentRequests/{request_id}/approve",
            json_data={"notes": notes},
        )

    async def reject_resident_request(
        self,
        request_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Reject a resident request (Admin/Manager)."""
        return await self._request(
            "POST",
            f"/api/ResidentRequests/{request_id}/reject",
            json_data={"reason": reason},
        )

    async def preverify_resident_request(self, request_id: str) -> Dict[str, Any]:
        """Run pre-verify checks for a resident request (Admin/Manager)."""
        return await self._request("GET", f"/api/ResidentRequests/{request_id}/pre-verify")

    async def get_resident_request_audit_logs(self, request_id: str) -> List[Dict]:
        """Get approval/rejection audit logs for a resident request."""
        return await self._request("GET", f"/api/ResidentRequests/{request_id}/audit-logs")

    async def update_resident_request(
        self,
        request_id: str,
        request_data_json: str,
    ) -> Dict[str, Any]:
        """Update resident request payload."""
        return await self._request(
            "PATCH",
            f"/api/ResidentRequests/{request_id}",
            json_data={"requestDataJson": request_data_json},
        )

    async def delete_resident_request(self, request_id: str) -> Dict[str, Any]:
        """Delete a resident request."""
        return await self._request("DELETE", f"/api/ResidentRequests/{request_id}")

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
        self,
        phone_number: str,
        unit_id: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
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
        if email:
            payload["email"] = email

        return await self._request("POST", "/api/ResidentRegistries", json_data=payload)

    async def get_resident_registry(self, registry_id: str) -> Dict[str, Any]:
        """Get resident registry entry by id."""
        return await self._request("GET", f"/api/ResidentRegistries/{registry_id}")

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

    async def bulk_update_resident_registry_status(
        self,
        registry_ids: List[str],
        status: str,
    ) -> Dict[str, Any]:
        """Bulk update resident registry statuses."""
        return await self._request(
            "PUT",
            "/api/ResidentRegistries/bulk/status",
            json_data={"ids": registry_ids, "status": status},
        )

    async def delete_resident_registry(self, registry_id: str) -> Dict[str, Any]:
        """Delete resident registry entry."""
        return await self._request("DELETE", f"/api/ResidentRegistries/{registry_id}")

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

    async def register_visitor(
        self,
        visitor_name: str,
        visit_date: str,
        visitor_phone: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a visitor for the caller's active unit.

        The current backend visitor flow persists visitor name and expected
        arrival only. Optional phone/purpose are appended for operator context.
        """
        unit_id = await self._get_current_active_unit_id()
        if not unit_id:
            raise PulseAPIError(
                "Unable to determine an active unit for visitor registration.",
                status_code=400,
            )

        extras: List[str] = []
        if visitor_phone:
            extras.append(f"SĐT: {visitor_phone.strip()}")
        if purpose:
            extras.append(f"Mục đích: {purpose.strip()}")

        display_name = visitor_name.strip()
        if extras:
            display_name = f"{display_name} ({' | '.join(extras)})"

        return await self._request(
            "POST",
            "/api/VisitorRegistrations",
            json_data={
                "unitId": unit_id,
                "visitorName": display_name,
                "expectedArrival": f"{visit_date}T09:00:00",
            },
        )

    # ==================== Units ====================

    async def get_building_overview(self) -> Dict[str, Any]:
        """Get building overview dashboard data."""
        return await self._request("GET", "/api/Buildings/overview")

    async def get_blocks(self) -> List[Dict]:
        """Get all building blocks."""
        return await self._request("GET", "/api/Blocks")

    async def get_block_floors(self, block_id: str) -> List[Dict]:
        """Get floors for a building block."""
        return await self._request("GET", f"/api/Blocks/{block_id}/floors")

    async def get_units(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get list of building units."""
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if status:
            params["status"] = status
        return await self._request("GET", "/api/Units", params=params)

    async def get_unit(self, unit_id: str) -> Dict[str, Any]:
        """Get unit detail by id."""
        return await self._request("GET", f"/api/Units/{unit_id}")

    async def create_unit(
        self,
        unit_number: str,
        floor_id: Optional[str] = None,
        unit_type_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a building unit."""
        return await self._request(
            "POST",
            "/api/Units",
            json_data={
                "unitNumber": unit_number,
                "floorId": floor_id,
                "unitTypeId": unit_type_id,
            },
        )

    async def update_unit_status(self, unit_id: str, status: str) -> Dict[str, Any]:
        """Update unit status."""
        return await self._request(
            "PUT",
            f"/api/Units/{unit_id}/status",
            json_data={"status": status},
        )

    async def get_resident_units(
        self,
        user_id: Optional[str] = None,
        unit_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get resident-unit mappings."""
        params: Dict[str, Any] = {}
        if user_id:
            params["userId"] = user_id
        if unit_id:
            params["unitId"] = unit_id
        return await self._request("GET", "/api/ResidentUnits", params=params)

    async def assign_resident_to_unit(
        self,
        user_id: str,
        unit_id: str,
        relationship: str,
        move_in_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assign a resident to a unit."""
        payload: Dict[str, Any] = {
            "userId": user_id,
            "unitId": unit_id,
            "relationship": relationship,
        }
        if move_in_date:
            payload["moveInDate"] = move_in_date
        return await self._request("POST", "/api/ResidentUnits", json_data=payload)

    # ==================== Access Cards ====================

    async def get_access_cards(self, user_id: Optional[str] = None) -> List[Dict]:
        """Get access cards for current scope or specific user."""
        params: Dict[str, Any] = {}
        if user_id:
            params["userId"] = user_id
        return await self._request("GET", "/api/AccessCards", params=params)

    async def get_access_card(self, card_id: str) -> Dict[str, Any]:
        """Get access card detail."""
        return await self._request("GET", f"/api/AccessCards/{card_id}")

    async def create_access_card(
        self,
        user_id: str,
        card_number: str,
        unit_id: Optional[str] = None,
        relationship: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new access card."""
        return await self._request(
            "POST",
            "/api/AccessCards",
            json_data={
                "userId": user_id,
                "cardNumber": card_number,
                "unitId": unit_id,
                "relationship": relationship,
            },
        )

    async def update_access_card_status(
        self,
        card_id: str,
        status: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update access card status."""
        payload: Dict[str, Any] = {"status": status}
        if reason:
            payload["reason"] = reason
        return await self._request(
            "PUT",
            f"/api/AccessCards/{card_id}/status",
            json_data=payload,
        )

    async def delete_access_card(self, card_id: str) -> Dict[str, Any]:
        """Delete an access card."""
        return await self._request("DELETE", f"/api/AccessCards/{card_id}")

    # ==================== Community Events ====================

    async def get_community_events(self, include_unpublished: bool = False) -> List[Dict]:
        """Get community events."""
        params = {"includeUnpublished": include_unpublished}
        return await self._request("GET", "/api/CommunityEvents", params=params)

    async def get_community_event(self, event_id: str) -> Dict[str, Any]:
        """Get community event detail."""
        return await self._request("GET", f"/api/CommunityEvents/{event_id}")

    async def create_community_event(
        self,
        title: str,
        description: str,
        location: str,
        start_at: str,
        end_at: str,
        capacity: int,
        is_published: bool = True,
    ) -> Dict[str, Any]:
        """Create a community event."""
        return await self._request(
            "POST",
            "/api/CommunityEvents",
            json_data={
                "createdBy": "00000000-0000-0000-0000-000000000000",
                "title": title,
                "description": description,
                "location": location,
                "startAt": start_at,
                "endAt": end_at,
                "capacity": capacity,
                "isPublished": is_published,
            },
        )

    async def register_community_event(self, event_id: str) -> Dict[str, Any]:
        """Register current user for a community event."""
        return await self._request("POST", f"/api/CommunityEvents/{event_id}/register")

    # ==================== Notifications ====================

    async def get_payment_history(
        self,
        bill_id: Optional[str] = None,
        paid_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Dict]:
        """Get payment history for the current accessible scope.

        Args:
            bill_id: Filter by bill ID
            paid_by: Filter by payer user ID
            page: Page number
            page_size: Page size

        Returns:
            List of payment records
        """
        params: Dict[str, Any] = {"page": page, "pageSize": page_size}
        if bill_id:
            params["billId"] = bill_id
        if paid_by:
            params["paidBy"] = paid_by
        endpoint = "/api/Payments/history" if await self._is_privileged_user() else "/api/v1/resident/payments/history"
        return await self._request("GET", endpoint, params=params)

    async def get_notifications(self, unread_only: bool = False) -> List[Dict]:
        """Get user notifications.

        Args:
            unread_only: Only return unread notifications

        Returns:
            List of notifications
        """
        params = {"isRead": False} if unread_only else {}
        return await self._request("GET", "/api/v1/resident/notifications", params=params)

    async def mark_notification_read(self, notification_id: str) -> Dict[str, Any]:
        """Mark notification as read.

        Args:
            notification_id: Notification ID

        Returns:
            Result
        """
        return await self._request("PUT", f"/api/v1/resident/notifications/{notification_id}/read")

    async def mark_all_notifications_read(self) -> Dict[str, Any]:
        """Mark all notifications as read."""
        return await self._request("PUT", "/api/v1/resident/notifications/read-all")

    async def get_unread_notification_count(self) -> Dict[str, Any]:
        """Get count of unread notifications."""
        notifications = await self.get_notifications(unread_only=True)
        return {"count": len(notifications)}

    # ==================== Announcements ====================

    async def get_announcements(self) -> List[Dict]:
        """Get building announcements.

        Args:
            limit: Maximum number of announcements

        Returns:
            List of announcements
        """
        return await self._request("GET", "/api/Announcements")

    async def get_announcement(self, announcement_id: str) -> Dict[str, Any]:
        """Get announcement details by ID."""
        return await self._request("GET", f"/api/Announcements/{announcement_id}")

    async def create_announcement(
        self,
        title: str,
        content: str,
        priority: str = "Normal",
    ) -> Dict[str, Any]:
        """Create a new announcement (Admin)."""
        return await self._request(
            "POST",
            "/api/Announcements",
            json_data={
                "createdBy": "00000000-0000-0000-0000-000000000000",
                "title": title,
                "content": content,
                "priority": priority,
            },
        )

    # ==================== User Roles & Permissions ====================

    async def get_users(self) -> List[Dict]:
        """Get all users."""
        return await self._request("GET", "/api/Users")

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get user detail by ID."""
        return await self._request("GET", f"/api/Users/{user_id}")

    async def get_user_overview(self) -> List[Dict]:
        """Get user overview with roles and units."""
        return await self._request("GET", "/api/Users/overview")

    async def get_users_by_roles(self, roles: List[str]) -> List[Dict]:
        """Get users filtered by role names."""
        return await self._request(
            "GET",
            "/api/Users/by-roles",
            params={"roles": ",".join(roles)},
        )

    async def create_privileged_user(
        self,
        full_name: str,
        email: str,
        password: str,
        role_name: str,
        phone_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create admin or staff account."""
        return await self._request(
            "POST",
            "/api/Users/admin-create",
            json_data={
                "fullName": full_name,
                "email": email,
                "password": password,
                "roleName": role_name,
                "phoneNumber": phone_number,
            },
        )

    async def create_resident_user(
        self,
        full_name: str,
        email: str,
        password: str,
        phone_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create resident account."""
        return await self._request(
            "POST",
            "/api/Users/resident-create",
            json_data={
                "fullName": full_name,
                "email": email,
                "password": password,
                "phoneNumber": phone_number,
            },
        )

    async def update_user_admin(
        self,
        user_id: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update user fields from admin/staff scope."""
        return await self._request(
            "PUT",
            f"/api/Users/{user_id}",
            json_data={
                "id": user_id,
                "fullName": full_name,
                "email": email,
                "status": status,
            },
        )

    async def deactivate_user(self, user_id: str) -> Dict[str, Any]:
        """Deactivate user account."""
        return await self._request("DELETE", f"/api/Users/{user_id}")

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
        return await self._request("GET", f"/api/Users/{user_id}/roles")

    async def assign_user_role(self, user_id: str, role_id: str) -> Dict[str, Any]:
        """Assign a role to a user."""
        return await self._request("POST", f"/api/Users/{user_id}/roles/{role_id}")

    async def remove_user_role(self, user_id: str, role_id: str) -> Dict[str, Any]:
        """Remove a role from a user."""
        return await self._request("DELETE", f"/api/Users/{user_id}/roles/{role_id}")

    async def get_roles(self) -> List[Dict]:
        """Get all roles."""
        return await self._request("GET", "/api/Roles")

    async def get_role_permissions(self, role_id: str) -> List[Dict]:
        """Get permissions assigned to a role."""
        return await self._request("GET", f"/api/Roles/{role_id}/permissions")

    async def create_role(self, role_name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Create a role."""
        return await self._request(
            "POST",
            "/api/Roles",
            json_data={"roleName": role_name, "description": description},
        )

    async def add_role_permission(self, role_id: str, permission_id: str) -> Dict[str, Any]:
        """Add a permission to a role."""
        return await self._request(
            "POST",
            f"/api/Roles/{role_id}/permissions",
            json_data=permission_id,
        )

    async def remove_role_permission(self, role_id: str, permission_id: str) -> Dict[str, Any]:
        """Remove a permission from a role."""
        return await self._request(
            "DELETE",
            f"/api/Roles/{role_id}/permissions/{permission_id}",
        )

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

    async def create_permission(self, resource: str, action: str) -> Dict[str, Any]:
        """Create a new permission."""
        return await self._request(
            "POST",
            "/api/Permissions",
            json_data={"resource": resource, "action": action},
        )


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
