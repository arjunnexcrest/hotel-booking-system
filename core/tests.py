from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import HotelMembership
from bookings.models import Booking
from hotels.models import Hotel, HotelDocument
from restaurants.models import OperatingHours, Restaurant
from tables.models import RestaurantTable

User = get_user_model()


class EndToEndWorkflowTests(APITestCase):
    """
    Comprehensive end-to-end workflow tests covering:
    1. Authentication & Role-Based Access Control
    2. Hotel Registration, Document Upload & Super-Admin Approval
    3. Restaurant & Table Management (Operating Hours, Bulk Create, Floor Plan, Stats)
    4. Customer Discovery, Live Table Availability, Reservation & Cancellation Lifecycle
    """

    def setUp(self):
        self.super_admin = User.objects.create_user(
            username='wf_admin',
            email='wf_admin@hotelbooking.com',
            password='Admin@12345',
            role=User.Role.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
            is_verified=True,
        )
        self.owner = User.objects.create_user(
            username='wf_owner',
            email='wf_owner@grandpalace.com',
            password='Owner@12345',
            role=User.Role.HOTEL_OWNER,
            phone_number='+91 9876543210',
            is_verified=True,
        )
        self.customer = User.objects.create_user(
            username='wf_customer',
            email='wf_customer@example.com',
            password='Customer@12345',
            role=User.Role.CUSTOMER,
            phone_number='+91 9123456789',
            is_verified=True,
        )
        self.staff_user = User.objects.create_user(
            username='wf_staff',
            email='wf_staff@grandpalace.com',
            password='Staff@12345',
            role=User.Role.STAFF,
            is_verified=True,
        )

    def _login(self, username, password):
        res = self.client.post(
            '/api/auth/token/',
            {'username': username, 'password': password},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res.data

    def _create_approved_hotel_stack(self):
        hotel = Hotel.objects.create(
            name='Grand Azure Palace',
            slug='grand-azure-palace-wf',
            owner=self.owner,
            description='Luxury heritage dining hotel',
            hotel_type='Luxury Hotel & Spa',
            email='concierge@grandazure.com',
            phone='+91 22 6677 8899',
            address='Marine Drive',
            city='Mumbai',
            state='Maharashtra',
            postal_code='400021',
            country='India',
            star_rating=5,
            amenities=['Pool', 'Valet Parking', 'Rooftop Bar'],
            status=Hotel.Status.APPROVED,
            is_active=True,
        )
        HotelMembership.objects.create(
            user=self.owner,
            hotel=hotel,
            role=HotelMembership.MembershipRole.OWNER,
            is_active=True,
        )
        HotelMembership.objects.create(
            user=self.staff_user,
            hotel=hotel,
            role=HotelMembership.MembershipRole.STAFF,
            is_active=True,
        )
        restaurant = Restaurant.objects.create(
            hotel=hotel,
            name='Azure Rooftop Lounge',
            slug='azure-rooftop-lounge',
            description='Fine dining rooftop venue',
            cuisine_type='Contemporary European & Italian',
            is_active=True,
        )
        for day in range(7):
            OperatingHours.objects.create(
                restaurant=restaurant,
                day_of_week=day,
                opening_time='10:00:00',
                closing_time='23:00:00',
                is_closed=False,
            )
        t1 = RestaurantTable.objects.create(
            restaurant=restaurant,
            table_number='T-1',
            capacity=4,
            min_capacity=2,
            table_type=RestaurantTable.TableType.STANDARD,
            zone_name='Main Hall',
            operational_status=RestaurantTable.OperationalStatus.AVAILABLE,
            is_active=True,
        )
        t2 = RestaurantTable.objects.create(
            restaurant=restaurant,
            table_number='T-2',
            capacity=6,
            min_capacity=2,
            table_type=RestaurantTable.TableType.VIP,
            zone_name='Terrace',
            operational_status=RestaurantTable.OperationalStatus.AVAILABLE,
            is_active=True,
        )
        t_maint = RestaurantTable.objects.create(
            restaurant=restaurant,
            table_number='T-9',
            capacity=4,
            min_capacity=1,
            table_type=RestaurantTable.TableType.STANDARD,
            zone_name='Main Hall',
            operational_status=RestaurantTable.OperationalStatus.MAINTENANCE,
            is_active=True,
        )
        return hotel, restaurant, t1, t2, t_maint

    # ── Workflow 1: Auth & RBAC ───────────────────────────────────────────────

    def test_auth_registration_login_and_profile_workflow(self):
        # Register new customer
        reg_res = self.client.post(
            '/api/accounts/users/',
            {
                'username': 'new_diner',
                'email': 'new_diner@example.com',
                'password': 'StrongPassword@123',
                'first_name': 'Aarav',
                'last_name': 'Mehta',
                'role': 'customer',
            },
            format='json',
        )
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)

        # Login with JWT
        tokens = self._login('new_diner', 'StrongPassword@123')
        self.assertIn('access', tokens)
        self.assertIn('refresh', tokens)

        # Fetch profile
        me_res = self.client.get('/api/accounts/users/me/')
        self.assertEqual(me_res.status_code, status.HTTP_200_OK)
        self.assertEqual(me_res.data['email'], 'new_diner@example.com')

        # Customer must NOT access super-admin pending approvals
        denied_res = self.client.get('/api/hotels/hotels/pending_approvals/')
        self.assertEqual(denied_res.status_code, status.HTTP_403_FORBIDDEN)

    # ── Workflow 2: Hotel Onboarding & Super-Admin Approval ───────────────────

    def test_hotel_registration_and_super_admin_approval_workflow(self):
        self._login('wf_owner', 'Owner@12345')

        create_res = self.client.post(
            '/api/hotels/hotels/',
            {
                'name': 'Royal Orchid Suites',
                'description': 'Boutique luxury suites and gourmet dining',
                'hotel_type': 'Boutique Heritage Hotel',
                'email': 'hello@royalorchid.com',
                'phone': '+91 80 4455 6677',
                'address': 'MG Road',
                'city': 'Bengaluru',
                'state': 'Karnataka',
                'postal_code': '560001',
                'country': 'India',
                'star_rating': 4,
            },
            format='json',
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED, create_res.data)
        slug = create_res.data['slug']
        hotel_id = create_res.data['id']
        self.assertEqual(create_res.data['status'], Hotel.Status.PENDING_APPROVAL)

        # Upload verification document
        doc_file = SimpleUploadedFile('license.pdf', b'%PDF-1.4 mock', content_type='application/pdf')
        HotelDocument.objects.create(
            hotel_id=hotel_id,
            document_type=HotelDocument.DocumentType.BUSINESS_LICENSE,
            file=doc_file,
        )

        # Public listing should NOT expose pending hotel
        self.client.credentials()
        public_list = self.client.get('/api/hotels/hotels/')
        self.assertEqual(public_list.status_code, status.HTTP_200_OK)
        results = public_list.data.get('results', public_list.data)
        self.assertFalse(any(h['slug'] == slug for h in results))

        # Super Admin reviews and approves
        self._login('wf_admin', 'Admin@12345')
        pending_res = self.client.get('/api/hotels/hotels/pending_approvals/')
        self.assertEqual(pending_res.status_code, status.HTTP_200_OK)
        pending_list = pending_res.data.get('results', pending_res.data)
        self.assertTrue(any(h['slug'] == slug for h in pending_list))

        approve_res = self.client.post(
            f'/api/hotels/hotels/{slug}/approve/',
            {'reason': 'All compliance documents verified'},
            format='json',
        )
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)

        # Public listing NOW exposes approved hotel
        self.client.credentials()
        public_list_after = self.client.get('/api/hotels/hotels/?city=Bengaluru')
        results_after = public_list_after.data.get('results', public_list_after.data)
        self.assertTrue(any(h['slug'] == slug for h in results_after))

    # ── Workflow 3: Restaurant & Table Management ─────────────────────────────

    def test_restaurant_and_table_management_workflow(self):
        hotel, _, _, _, _ = self._create_approved_hotel_stack()
        self._login('wf_owner', 'Owner@12345')

        # Create restaurant
        rest_res = self.client.post(
            '/api/restaurants/restaurants/',
            {
                'hotel': hotel.id,
                'name': 'Saffron Grill',
                'cuisine_type': 'Modern Indian Fine Dining',
                'description': 'Signature tandoor & coastal specialties',
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(rest_res.status_code, status.HTTP_201_CREATED, rest_res.data)
        rest_id = rest_res.data['id']

        # Bulk set weekly operating hours (0=Mon..6=Sun)
        schedule = [
            {
                'day_of_week': d,
                'opening_time': '11:00:00',
                'closing_time': '23:00:00',
                'is_closed': False,
            }
            for d in range(7)
        ]
        hours_res = self.client.post(
            f'/api/restaurants/restaurants/{rest_id}/bulk_operating_hours/',
            schedule,
            format='json',
        )
        self.assertEqual(hours_res.status_code, status.HTTP_200_OK, hours_res.data)

        # Bulk create tables under /api/tables/tables/
        bulk_res = self.client.post(
            '/api/tables/tables/bulk_create/',
            {
                'restaurant': rest_id,
                'prefix': 'SG-',
                'start_number': 1,
                'count': 3,
                'capacity': 4,
                'min_capacity': 2,
                'table_type': 'STANDARD',
                'shape': 'ROUND',
                'zone_name': 'Garden',
            },
            format='json',
        )
        self.assertEqual(bulk_res.status_code, status.HTTP_201_CREATED, bulk_res.data)
        self.assertEqual(bulk_res.data['created_count'], 3)
        table_id = bulk_res.data['tables'][0]['id']

        # Update table operational status
        status_res = self.client.post(
            f'/api/tables/tables/{table_id}/update_status/',
            {'operational_status': 'OCCUPIED', 'reason': 'Walk-in party seated'},
            format='json',
        )
        self.assertEqual(status_res.status_code, status.HTTP_200_OK)

        # Verify floor_plan & stats endpoints
        fp_res = self.client.get(f'/api/restaurants/restaurants/{rest_id}/floor_plan/')
        self.assertEqual(fp_res.status_code, status.HTTP_200_OK)
        self.assertIn('Garden', fp_res.data['zones'])
        self.assertEqual(fp_res.data['total_tables'], 3)

        stats_res = self.client.get(f'/api/restaurants/restaurants/{rest_id}/stats/')
        self.assertEqual(stats_res.status_code, status.HTTP_200_OK)
        self.assertEqual(stats_res.data['occupied'], 1)
        self.assertEqual(stats_res.data['available'], 2)

    # ── Workflow 4: Customer Discovery, Availability & Booking Lifecycle ──────

    def test_customer_availability_booking_conflict_and_lifecycle_workflow(self):
        hotel, restaurant, t1, t2, t_maint = self._create_approved_hotel_stack()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        today_str = timezone.localdate().isoformat()

        # 1. Public slots check for TODAY (regression test for naive vs aware datetime bug)
        today_slots = self.client.get(
            f'/api/bookings/bookings/available_slots/?restaurant={restaurant.id}&date={today_str}&guests=2'
        )
        self.assertEqual(today_slots.status_code, status.HTTP_200_OK)

        # 2. Public slots check for TOMORROW
        slots_res = self.client.get(
            f'/api/bookings/bookings/available_slots/?restaurant={restaurant.id}&date={tomorrow}&guests=2&duration_minutes=90'
        )
        self.assertEqual(slots_res.status_code, status.HTTP_200_OK)
        self.assertGreater(slots_res.data['total_slots'], 0)

        # 3. Check availability excludes MAINTENANCE table
        avail_res = self.client.get(
            f'/api/bookings/bookings/check_availability/?restaurant={restaurant.id}&date={tomorrow}&start_time=19:00&end_time=20:30&guests=2'
        )
        self.assertEqual(avail_res.status_code, status.HTTP_200_OK)
        avail_ids = {t['id'] for t in avail_res.data['tables']}
        self.assertIn(t1.id, avail_ids)
        self.assertIn(t2.id, avail_ids)
        self.assertNotIn(t_maint.id, avail_ids)

        # 4. Authenticated customer creates booking on T-1
        self._login('wf_customer', 'Customer@12345')
        book_res = self.client.post(
            '/api/bookings/bookings/',
            {
                'hotel': hotel.id,
                'restaurant': restaurant.id,
                'table': t1.id,
                'booking_date': tomorrow,
                'start_time': '19:00',
                'end_time': '20:30',
                'guest_count': 3,
                'customer_name': 'John Doe',
                'customer_email': 'wf_customer@example.com',
                'customer_phone': '+91 9123456789',
                'special_requests': 'Window seat please',
            },
            format='json',
        )
        self.assertEqual(book_res.status_code, status.HTTP_201_CREATED, book_res.data)
        booking_id = book_res.data['id']
        booking_ref = book_res.data['booking_reference']

        # 5. Double-booking conflict on same table & overlapping window MUST fail
        conflict_res = self.client.post(
            '/api/bookings/bookings/',
            {
                'hotel': hotel.id,
                'restaurant': restaurant.id,
                'table': t1.id,
                'booking_date': tomorrow,
                'start_time': '19:30',
                'end_time': '21:00',
                'guest_count': 2,
                'customer_name': 'Conflict Guest',
                'customer_email': 'conflict@example.com',
                'customer_phone': '+91 9000000000',
            },
            format='json',
        )
        self.assertEqual(conflict_res.status_code, status.HTTP_400_BAD_REQUEST)

        # 6. Auto-assign booking picks T-2 (never T-9 MAINTENANCE)
        auto_res = self.client.post(
            '/api/bookings/bookings/',
            {
                'hotel': hotel.id,
                'restaurant': restaurant.id,
                'table': None,
                'booking_date': tomorrow,
                'start_time': '19:00',
                'end_time': '20:30',
                'guest_count': 2,
                'customer_name': 'Guest Auto',
                'customer_email': 'guest_auto@example.com',
                'customer_phone': '+91 9888888888',
            },
            format='json',
        )
        self.assertEqual(auto_res.status_code, status.HTTP_201_CREATED, auto_res.data)
        self.assertEqual(auto_res.data['table'], t2.id)
        auto_ref = auto_res.data['booking_reference']

        # 7. Customer my_bookings returns upcoming reservations
        my_res = self.client.get('/api/bookings/bookings/my_bookings/')
        self.assertEqual(my_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(my_res.data['upcoming']), 1)

        # 8. Guest cancels auto-assigned reservation by reference
        self.client.credentials()
        guest_cancel = self.client.post(
            '/api/bookings/bookings/cancel_by_reference/',
            {
                'booking_reference': auto_ref,
                'customer_email': 'guest_auto@example.com',
                'reason': 'Schedule changed',
            },
            format='json',
        )
        self.assertEqual(guest_cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(guest_cancel.data['booking_status'], Booking.BookingStatus.CANCELLED)

        # 9. Staff checks in and completes customer booking
        self._login('wf_staff', 'Staff@12345')
        checkin_res = self.client.post(f'/api/bookings/bookings/{booking_id}/check_in/')
        self.assertEqual(checkin_res.status_code, status.HTTP_200_OK)
        self.assertEqual(checkin_res.data['table_status'], RestaurantTable.OperationalStatus.OCCUPIED)

        complete_res = self.client.post(f'/api/bookings/bookings/{booking_id}/complete/')
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            complete_res.data['table_status'],
            RestaurantTable.OperationalStatus.AWAITING_CLEANING,
        )
        self.assertTrue(bool(booking_ref))
