from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import HotelMembership
from bookings.models import Booking
from hotels.models import Hotel
from restaurants.models import Restaurant, OperatingHours
from tables.models import RestaurantTable
from staff.models import Staff

User = get_user_model()


class Command(BaseCommand):
    help = 'Populates the database with initial demo data for testing.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting demo data seeding...'))

        # 1. Super Admin
        super_admin, created = User.objects.get_or_create(
            username='admin',
            email='admin@hotelbooking.com',
            defaults={
                'first_name': 'Super',
                'last_name': 'Admin',
                'role': User.Role.SUPER_ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
            }
        )
        if created:
            super_admin.set_password('Admin@12345')
            super_admin.save()
            self.stdout.write(self.style.SUCCESS('Created Super Admin: admin@hotelbooking.com (Admin@12345)'))
        else:
            self.stdout.write('Super Admin already exists.')

        # 2. Hotel Owner
        hotel_owner, created = User.objects.get_or_create(
            username='owner_palace',
            email='owner@grandpalace.com',
            defaults={
                'first_name': 'Vikram',
                'last_name': 'Singhania',
                'role': User.Role.HOTEL_OWNER,
                'phone_number': '+91 9876543210',
                'is_verified': True,
            }
        )
        if created:
            hotel_owner.set_password('Owner@12345')
            hotel_owner.save()
            self.stdout.write(self.style.SUCCESS('Created Hotel Owner: owner@grandpalace.com (Owner@12345)'))

        # 3. Customer
        customer, created = User.objects.get_or_create(
            username='customer_john',
            email='john@example.com',
            defaults={
                'first_name': 'John',
                'last_name': 'Doe',
                'role': User.Role.CUSTOMER,
                'phone_number': '+91 9123456789',
                'is_verified': True,
            }
        )
        if created:
            customer.set_password('Customer@12345')
            customer.save()
            self.stdout.write(self.style.SUCCESS('Created Customer: john@example.com (Customer@12345)'))

        # 4. Hotel
        hotel, created = Hotel.objects.get_or_create(
            slug='grand-azure-palace',
            defaults={
                'name': 'The Grand Azure Palace & Suites',
                'owner': hotel_owner,
                'description': 'A luxury 5-star hotel offering world-class dining, magnificent city views, and AI-assisted table service.',
                'hotel_type': 'Luxury Heritage & Business Hotel',
                'email': 'concierge@grandazure.com',
                'phone': '+91 22 6677 8899',
                'address': 'Marine Drive, Nariman Point',
                'city': 'Mumbai',
                'state': 'Maharashtra',
                'postal_code': '400021',
                'country': 'India',
                'star_rating': 5,
                'amenities': ['Infinity Pool', 'Valet Parking', 'Rooftop Lounge', 'Free Wi-Fi', 'Spa'],
                'status': Hotel.Status.APPROVED,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Hotel: {hotel.name}'))

        # Add Hotel Membership for owner
        HotelMembership.objects.get_or_create(
            user=hotel_owner,
            hotel=hotel,
            role=HotelMembership.MembershipRole.OWNER,
            defaults={'is_active': True}
        )

        # 5. Second Hotel for listing demonstration
        hotel2, created = Hotel.objects.get_or_create(
            slug='serena-bay-resort',
            defaults={
                'name': 'Serena Bay Luxury Resort',
                'owner': hotel_owner,
                'description': 'Coastal waterfront resort featuring exquisite open-air dining, fresh seafood, and tranquil garden ambience.',
                'hotel_type': 'Resort & Fine Dining',
                'email': 'reservations@serenabay.com',
                'phone': '+91 832 245 6789',
                'address': 'Candolim Beach Road',
                'city': 'Goa',
                'state': 'Goa',
                'postal_code': '403515',
                'country': 'India',
                'star_rating': 5,
                'amenities': ['Private Beach', 'Poolside Bar', 'Live Seafood Grill', 'Airport Shuttle'],
                'status': Hotel.Status.APPROVED,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Hotel: {hotel2.name}'))

        HotelMembership.objects.get_or_create(
            user=hotel_owner,
            hotel=hotel2,
            role=HotelMembership.MembershipRole.OWNER,
            defaults={'is_active': True}
        )

        # 5b. Pending Hotel for Super-Admin Approval Demo
        pending_hotel, created = Hotel.objects.get_or_create(
            slug='emerald-crest-heritage',
            defaults={
                'name': 'Emerald Crest Heritage Haveli',
                'owner': hotel_owner,
                'description': 'Restored royal courtyard property with private dining terraces and artisanal Rajasthani cuisine.',
                'hotel_type': 'Boutique Heritage Hotel',
                'email': 'concierge@emeraldcrest.com',
                'phone': '+91 141 267 8900',
                'address': 'Civil Lines Heritage Avenue',
                'city': 'Jaipur',
                'state': 'Rajasthan',
                'postal_code': '302006',
                'country': 'India',
                'star_rating': 4,
                'amenities': ['Courtyard Dining', 'Valet Parking', 'Live Folk Music'],
                'status': Hotel.Status.PENDING_APPROVAL,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Pending Hotel (for approval demo): {pending_hotel.name}'))

        # 6. Restaurant under Grand Azure Palace
        restaurant, created = Restaurant.objects.get_or_create(
            hotel=hotel,
            slug='the-royal-spice-lounge',
            defaults={
                'name': 'The Royal Spice Lounge',
                'description': 'Authentic North Indian, Awadhi and Mughlai culinary masterworks served in a regal ambience.',
                'cuisine_type': 'Indian Fine Dining & Mughlai',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Restaurant: {restaurant.name}'))

        # Operating hours for all days
        for day in range(7):
            OperatingHours.objects.get_or_create(
                restaurant=restaurant,
                day_of_week=day,
                defaults={
                    'opening_time': '11:00:00',
                    'closing_time': '23:30:00',
                    'is_closed': False,
                }
            )

        # 7. Tables in Restaurant
        table_configs = [
            ('T-01', 2, 1, RestaurantTable.TableType.STANDARD, 'Window Side'),
            ('T-02', 2, 1, RestaurantTable.TableType.STANDARD, 'Window Side'),
            ('T-03', 4, 2, RestaurantTable.TableType.BOOTH, 'Main Dining Hall'),
            ('T-04', 4, 2, RestaurantTable.TableType.BOOTH, 'Main Dining Hall'),
            ('T-05', 6, 4, RestaurantTable.TableType.STANDARD, 'Garden Terrace'),
            ('T-06', 8, 4, RestaurantTable.TableType.VIP, 'Private Dining Suite'),
        ]
        for num, cap, min_c, t_type, zone in table_configs:
            RestaurantTable.objects.get_or_create(
                restaurant=restaurant,
                table_number=num,
                defaults={
                    'capacity': cap,
                    'min_capacity': min_c,
                    'table_type': t_type,
                    'zone_name': zone,
                    'operational_status': RestaurantTable.OperationalStatus.AVAILABLE,
                    'is_active': True,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'Created/verified 6 tables for {restaurant.name}'))

        # 8. Staff member
        staff_user, created = User.objects.get_or_create(
            username='staff_rahul',
            email='waiter@grandpalace.com',
            defaults={
                'first_name': 'Rahul',
                'last_name': 'Sharma',
                'role': User.Role.STAFF,
                'phone_number': '+91 9988776655',
                'is_verified': True,
            }
        )
        if created:
            staff_user.set_password('Staff@12345')
            staff_user.save()
            self.stdout.write(self.style.SUCCESS('Created Staff user: waiter@grandpalace.com (Staff@12345)'))

        Staff.objects.get_or_create(
            hotel=hotel,
            user=staff_user,
            defaults={
                'employee_id': 'EMP-AZURE-007',
                'role': Staff.StaffRole.WAITER,
                'phone': '+91 9988776655',
                'is_active': True,
            }
        )

        HotelMembership.objects.get_or_create(
            user=staff_user,
            hotel=hotel,
            role=HotelMembership.MembershipRole.STAFF,
            defaults={'is_active': True}
        )

        # 9. Restaurant & tables under Serena Bay Resort (Goa)
        rest2, created = Restaurant.objects.get_or_create(
            hotel=hotel2,
            slug='coastal-breeze-deck',
            defaults={
                'name': 'Coastal Breeze Deck',
                'description': 'Open-air oceanfront dining specializing in grilled catch of the day and Mediterranean tapas.',
                'cuisine_type': 'Mediterranean & Seafood',
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Restaurant: {rest2.name}'))
        for day in range(7):
            OperatingHours.objects.get_or_create(
                restaurant=rest2,
                day_of_week=day,
                defaults={
                    'opening_time': '12:00:00',
                    'closing_time': '23:00:00',
                    'is_closed': False,
                }
            )
        for num, cap, min_c, t_type, zone in [
            ('G-01', 2, 1, RestaurantTable.TableType.OUTDOOR, 'Ocean Deck'),
            ('G-02', 4, 2, RestaurantTable.TableType.OUTDOOR, 'Ocean Deck'),
            ('G-03', 6, 3, RestaurantTable.TableType.VIP, 'Sunset Cabana'),
        ]:
            RestaurantTable.objects.get_or_create(
                restaurant=rest2,
                table_number=num,
                defaults={
                    'capacity': cap,
                    'min_capacity': min_c,
                    'table_type': t_type,
                    'zone_name': zone,
                    'operational_status': RestaurantTable.OperationalStatus.AVAILABLE,
                    'is_active': True,
                }
            )

        # 10. Sample upcoming & completed bookings for customer demo
        first_table = RestaurantTable.objects.filter(restaurant=restaurant, table_number='T-03').first()
        if first_table:
            tomorrow = date.today() + timedelta(days=1)
            yesterday = date.today() - timedelta(days=1)
            Booking.objects.get_or_create(
                customer=customer,
                hotel=hotel,
                restaurant=restaurant,
                table=first_table,
                booking_date=tomorrow,
                start_time='19:00:00',
                defaults={
                    'end_time': '20:30:00',
                    'guest_count': 4,
                    'customer_name': 'John Doe',
                    'customer_email': customer.email,
                    'customer_phone': customer.phone_number,
                    'special_requests': 'Anniversary dinner — quiet booth preferred',
                    'booking_status': Booking.BookingStatus.CONFIRMED,
                }
            )
            Booking.objects.get_or_create(
                customer=customer,
                hotel=hotel,
                restaurant=restaurant,
                table=first_table,
                booking_date=yesterday,
                start_time='13:00:00',
                defaults={
                    'end_time': '14:30:00',
                    'guest_count': 2,
                    'customer_name': 'John Doe',
                    'customer_email': customer.email,
                    'customer_phone': customer.phone_number,
                    'special_requests': 'Lunch tasting menu',
                    'booking_status': Booking.BookingStatus.COMPLETED,
                }
            )

        self.stdout.write(self.style.SUCCESS('=== Demo data seeding completed successfully! ==='))
