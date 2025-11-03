"""Unit tests for sign-up functionality."""
import pytest
from streamlit_app.auth import validate_email, validate_password, get_password_strength


class TestEmailValidation:
    """Test email validation function."""
    
    def test_valid_email(self):
        """Test that valid emails pass validation."""
        valid_emails = [
            "test@example.com",
            "user.name@example.co.uk",
            "first+last@test.org",
            "test123@example.com",
        ]
        
        for email in valid_emails:
            valid, error = validate_email(email)
            assert valid is True, f"Expected {email} to be valid"
            assert error is None, f"Expected no error for {email}"
    
    def test_invalid_email_format(self):
        """Test that invalid email formats fail validation."""
        invalid_emails = [
            "not-an-email",
            "missing@domain",
            "@example.com",
            "user@",
            "user name@example.com",
            "",
        ]
        
        for email in invalid_emails:
            valid, error = validate_email(email)
            assert valid is False, f"Expected {email} to be invalid"
            assert error is not None, f"Expected error message for {email}"
    
    def test_empty_email(self):
        """Test that empty email returns appropriate error."""
        valid, error = validate_email("")
        assert valid is False
        assert "required" in error.lower()


class TestPasswordValidation:
    """Test password validation function."""
    
    def test_valid_password(self):
        """Test that valid passwords pass validation."""
        valid_passwords = [
            "Test1234",
            "MyPassword123",
            "Secure!Pass1",
            "aBcD1234",
        ]
        
        for password in valid_passwords:
            valid, errors = validate_password(password)
            assert valid is True, f"Expected {password} to be valid, got errors: {errors}"
            assert len(errors) == 0, f"Expected no errors for {password}"
    
    def test_short_password(self):
        """Test that passwords shorter than 8 characters fail."""
        short_passwords = ["Test1", "Abc123", "Pass1"]
        
        for password in short_passwords:
            valid, errors = validate_password(password)
            assert valid is False, f"Expected {password} to be invalid"
            assert any("8 characters" in error for error in errors)
    
    def test_missing_uppercase(self):
        """Test that passwords without uppercase fail."""
        password = "password123"
        valid, errors = validate_password(password)
        assert valid is False
        assert any("uppercase" in error.lower() for error in errors)
    
    def test_missing_lowercase(self):
        """Test that passwords without lowercase fail."""
        password = "PASSWORD123"
        valid, errors = validate_password(password)
        assert valid is False
        assert any("lowercase" in error.lower() for error in errors)
    
    def test_missing_number(self):
        """Test that passwords without numbers fail."""
        password = "PasswordOnly"
        valid, errors = validate_password(password)
        assert valid is False
        assert any("number" in error.lower() for error in errors)
    
    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are returned."""
        password = "weak"  # Too short, no uppercase, no number
        valid, errors = validate_password(password)
        assert valid is False
        assert len(errors) >= 2  # Should have multiple errors


class TestPasswordStrength:
    """Test password strength indicator."""
    
    def test_empty_password(self):
        """Test that empty password returns 'None' strength."""
        strength, color = get_password_strength("")
        assert strength == "None"
        assert color == "gray"
    
    def test_weak_password(self):
        """Test that weak passwords are identified."""
        weak_passwords = ["Test1", "Pass12"]  # Very short, minimal requirements
        
        for password in weak_passwords:
            strength, color = get_password_strength(password)
            # Should be weak or medium for minimal passwords
            assert strength in ["Weak", "Medium"]
            assert color in ["red", "orange"]
    
    def test_medium_password(self):
        """Test that medium strength passwords are identified."""
        medium_passwords = [
            "Test12345",  # 9 chars with mixed case and numbers
            "MyPassword1",  # 12 chars but no special
        ]
        
        for password in medium_passwords:
            strength, color = get_password_strength(password)
            # Should be at least medium (could be strong)
            assert strength in ["Medium", "Strong"]
    
    def test_strong_password(self):
        """Test that strong passwords are identified."""
        strong_passwords = [
            "MySecure!Pass123",  # Long with special chars
            "Test@1234567890",  # Special chars and long
            "Sup3r$ecur3P@ssw0rd!",  # All requirements met
        ]
        
        for password in strong_passwords:
            strength, color = get_password_strength(password)
            assert strength == "Strong"
            assert color == "green"
    
    def test_strength_progression(self):
        """Test that strength increases with better passwords."""
        passwords = [
            "Test12",  # Weaker
            "Test12345",  # Better
            "Test@12345",  # Even better
        ]
        
        strengths = [get_password_strength(p)[0] for p in passwords]
        
        # All should be valid strength levels
        for strength in strengths:
            assert strength in ["Weak", "Medium", "Strong"]
        
        # Subsequent passwords should be same or better strength
        strength_order = {"Weak": 0, "Medium": 1, "Strong": 2}
        for i in range(len(strengths) - 1):
            assert strength_order[strengths[i]] <= strength_order[strengths[i + 1]]


class TestPasswordValidationEdgeCases:
    """Test edge cases in password validation."""
    
    def test_exactly_8_characters(self):
        """Test password with exactly 8 characters."""
        password = "Test1234"
        valid, errors = validate_password(password)
        assert valid is True
    
    def test_very_long_password(self):
        """Test that very long passwords are accepted."""
        password = "T" + "e" * 100 + "st1234"  # Very long password
        valid, errors = validate_password(password)
        assert valid is True
    
    def test_special_characters(self):
        """Test that special characters are allowed."""
        passwords_with_special = [
            "Test123!",
            "Pass@word1",
            "My#Secure1Pass",
            "Test_123_Password",
        ]
        
        for password in passwords_with_special:
            valid, errors = validate_password(password)
            assert valid is True, f"Expected {password} to be valid"
    
    def test_unicode_characters(self):
        """Test passwords with unicode characters."""
        # Password with unicode should still validate based on ASCII requirements
        password = "Test1234你好"
        valid, errors = validate_password(password)
        # Should be valid as it meets all requirements
        assert valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
