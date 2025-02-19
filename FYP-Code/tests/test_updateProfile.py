import unittest
from flask import json
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock APScheduler before importing app
sys.modules['apscheduler.schedulers.background'] = MagicMock()
sys.modules['apscheduler'] = MagicMock()

from app import create_app

class TestUpdateProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create main mock client and database structure
        cls.mock_client = MagicMock()
        cls.db = MagicMock()
        cls.mock_gridfs_db = MagicMock()
        cls.users_collection = MagicMock()
        cls.profiles_collection = MagicMock()

        # Setup mock database structure
        cls.mock_client.__getitem__.side_effect = lambda x: {
            'traffic-users': cls.db,
            'TSUN-TESTING': cls.mock_gridfs_db
        }.get(x, MagicMock())

        # Setup collections
        cls.db.__getitem__.side_effect = lambda x: {
            'users': cls.users_collection,
            'profiles': cls.profiles_collection
        }.get(x, MagicMock())

        # Mock users collection methods
        def mock_user_find_one(query):
            if query.get('username') == 'admin_user':
                return {
                    'id': 1,
                    'username': 'admin_user',
                    'user_profile': 'system_admin'
                }
            return None

        # Mock profiles collection methods
        def mock_profile_find_one(query):
            profile_name = query.get('user_profile')
            if profile_name == 'system_admin':
                return {
                    'user_profile': 'system_admin',
                    'permissions': {'manage_users': True}
                }
            elif profile_name == 'new_profile':
                return {
                    'user_profile': 'new_profile',
                    'permissions': {'manage_users': False}
                }
            elif profile_name == 'existing_profile':
                return {
                    'user_profile': 'existing_profile',
                    'permissions': {'manage_users': False}
                }
            return None

        def mock_update_one(query, update):
            old_profile = query.get('user_profile')
            if old_profile == 'existing_profile':
                return MagicMock(matched_count=1, modified_count=1)
            return MagicMock(matched_count=0, modified_count=0)

        cls.users_collection.find_one = MagicMock(side_effect=mock_user_find_one)
        cls.profiles_collection.find_one = MagicMock(side_effect=mock_profile_find_one)
        cls.profiles_collection.update_one = MagicMock(side_effect=mock_update_one)

    def setUp(self):
        with patch('gridfs.GridFS') as mock_gridfs:
            self.app = create_app(db_client=self.mock_client)
            self.client = self.app.test_client()

    def test_update_profile_unauthorized(self):
        """Test updating profile without proper authorization"""
        response = self.client.put('/api/profiles/existing_profile', json={
            "user_profile": "new_profile"
        })
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertEqual(data['message'], 'Unauthorized')

    def test_update_profile_success(self):
        """Test successful profile update"""
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin_user'
            sess['role'] = 'system_admin'

        response = self.client.put('/api/profiles/existing_profile', json={
            "user_profile": "updated_profile"
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['message'], 'Profile updated successfully')

    def test_update_profile_not_found(self):
        """Test updating non-existent profile"""
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin_user'
            sess['role'] = 'system_admin'

        response = self.client.put('/api/profiles/nonexistent_profile', json={
            "user_profile": "updated_profile"
        })
        self.assertEqual(response.status_code, 404)  # Changed back to 404 to match app's response
        data = json.loads(response.data)
        self.assertEqual(data['message'], 'Profile not found')

    def test_update_profile_duplicate_name(self):
        """Test updating to an existing profile name"""
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin_user'
            sess['role'] = 'system_admin'

        response = self.client.put('/api/profiles/existing_profile', json={
            "user_profile": "new_profile"  # This profile name already exists
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['message'], 'Profile name already exists')

if __name__ == '__main__':
    unittest.main()
