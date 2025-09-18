"""
Comprehensive tests for auto-cleanup functionality of dynamically generated Docker images.

This test suite validates:
- Enhanced cleanup logic with error handling
- Integration between orchestrator and SmartImageManager
- Configurable cleanup policies
- Monitoring and reporting capabilities
- Edge cases and error scenarios
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from biocage import BioCageOrchestrator
from biocage.intelligence import SmartImageManager
from biocage.container.docker_client import DockerClient, DockerCommandError


class TestAutoCleanup:
    """Test suite for auto-cleanup functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Mock docker client to avoid actual Docker calls
        self.mock_docker_client = Mock(spec=DockerClient)
        
        # Mock SmartImageManager with proper attributes
        self.mock_smart_image_manager = Mock(spec=SmartImageManager)
        self.mock_smart_image_manager.docker_client = self.mock_docker_client
        self.mock_smart_image_manager.image_cache = {}
        self.mock_smart_image_manager._get_image_size = Mock(return_value=0)
        self.mock_smart_image_manager._image_exists = Mock(return_value=False)
        self.mock_smart_image_manager.get_cache_info = Mock(return_value={"total_cached_images": 0, "cache_entries": []})
        
        # Create orchestrator with mocked dependencies
        self.orchestrator = BioCageOrchestrator(
            auto_detect_dependencies=True,
            auto_cleanup_dynamic_images=True,
            cleanup_policy="combined",
            cleanup_max_age=3600,  # 1 hour
            cleanup_max_count=5,
            cleanup_max_size_mb=100
        )
        
        # Replace the smart_image_manager with our mock
        self.orchestrator.smart_image_manager = self.mock_smart_image_manager

    def test_orchestrator_initialization_with_cleanup_config(self):
        """Test that orchestrator initializes with cleanup configuration."""
        orchestrator = BioCageOrchestrator(
            cleanup_policy="age",
            cleanup_max_age=7200,
            cleanup_max_count=10,
            cleanup_max_size_mb=500,
            cleanup_exclude_patterns=["important-*", "base-image"]
        )
        
        assert orchestrator.cleanup_policy == "age"
        assert orchestrator.cleanup_max_age == 7200
        assert orchestrator.cleanup_max_count == 10
        assert orchestrator.cleanup_max_size_mb == 500
        assert "important-*" in orchestrator.cleanup_exclude_patterns
        assert "base-image" in orchestrator.cleanup_exclude_patterns

    def test_cleanup_dynamic_images_basic(self):
        """Test basic dynamic image cleanup functionality."""
        # Set up mock images
        self.orchestrator._dynamic_images_created = {"biocage-auto:test1", "biocage-auto:test2"}
        
        # Mock image existence and size
        self.mock_docker_client.list_images.return_value = ["biocage-auto:test1"]
        self.mock_docker_client.run_command.side_effect = [
            # Image size command
            Mock(stdout="500MB"),
            # Container list command (no containers)
            Mock(stdout=""),
            # Image removal command
            Mock(stdout="Image removed")
        ]
        
        # Mock image size calculation
        with patch.object(self.orchestrator, '_get_image_size', return_value=500 * 1024 * 1024):
            with patch.object(self.orchestrator, '_image_exists', side_effect=[True, False]):
                self.orchestrator._cleanup_dynamic_images()
        
        # Verify cleanup was attempted
        assert self.mock_docker_client.run_command.call_count >= 1

    def test_cleanup_with_retry_logic(self):
        """Test cleanup retry logic for failed removals."""
        self.orchestrator._dynamic_images_created = {"biocage-auto:retry-test"}
        
        # Mock image exists but removal fails twice then succeeds
        self.mock_docker_client.list_images.return_value = ["biocage-auto:retry-test"]
        
        # Track call count for different command types
        call_count = 0
        
        def mock_run_command(command):
            nonlocal call_count
            call_count += 1
            
            if command == ["docker", "images", "biocage-auto:retry-test", "--format", "{{.Size}}"]:
                return Mock(stdout="100MB")
            elif command == ["docker", "ps", "-a", "--filter", "ancestor=biocage-auto:retry-test", "--format", "{{.ID}}"]:
                return Mock(stdout="")  # No containers
            elif command == ["docker", "rmi", "-f", "biocage-auto:retry-test"]:
                if call_count <= 6:  # First two attempts (calls 3 and 6)
                    raise DockerCommandError("Removal failed", [], 1, "Error")
                else:  # Third attempt (call 9)
                    return Mock(stdout="Image removed")
            return Mock(stdout="")
        
        self.mock_docker_client.run_command.side_effect = mock_run_command
        
        with patch.object(self.orchestrator, '_get_image_size', return_value=100 * 1024 * 1024):
            with patch.object(self.orchestrator, '_image_exists', return_value=True):
                with patch('time.sleep'):  # Mock sleep to speed up test
                    self.orchestrator._cleanup_dynamic_images()
        
        # Verify multiple removal attempts were made
        removal_calls = [call for call in self.mock_docker_client.run_command.call_args_list 
                        if call[0][0] == ["docker", "rmi", "-f", "biocage-auto:retry-test"]]
        assert len(removal_calls) == 3  # Should have retried 3 times

    def test_cleanup_containers_using_image(self):
        """Test that containers using an image are properly cleaned up."""
        # Mock containers using the image
        self.mock_docker_client.run_command.side_effect = [
            Mock(stdout="container1\ncontainer2"),  # Container list
            Mock(stdout=""),  # Stop container1
            Mock(stdout=""),  # Remove container1
            Mock(stdout=""),  # Stop container2
            Mock(stdout="")   # Remove container2
        ]
        
        self.orchestrator._cleanup_containers_using_image("test-image", self.mock_docker_client)
        
        # Verify container cleanup commands were called
        expected_calls = [
            (["docker", "ps", "-a", "--filter", "ancestor=test-image", "--format", "{{.ID}}"],),
            (["docker", "stop", "container1"],),
            (["docker", "rm", "-f", "container1"],),
            (["docker", "stop", "container2"],),
            (["docker", "rm", "-f", "container2"],)
        ]
        
        actual_calls = [call[0] for call in self.mock_docker_client.run_command.call_args_list]
        for expected_call in expected_calls:
            assert expected_call in actual_calls

    def test_smart_cleanup_integration(self):
        """Test integration with SmartImageManager cleanup."""
        # Mock SmartImageManager cleanup result
        cleanup_result = {
            "removed_count": 3,
            "failed_count": 1,
            "space_saved_bytes": 150 * 1024 * 1024,
            "total_images_before": 10,
            "total_images_after": 7,
            "policy_used": "combined"
        }
        
        self.mock_smart_image_manager.cleanup_old_images.return_value = cleanup_result
        
        # Perform smart cleanup
        result = self.orchestrator.perform_smart_cleanup()
        
        # Verify SmartImageManager was called with correct parameters
        self.mock_smart_image_manager.cleanup_old_images.assert_called_once_with(
            max_age=3600,
            policy="combined",
            max_count=5,
            max_size_mb=100,
            exclude_patterns=[]
        )
        
        # Verify result and statistics update
        assert result == cleanup_result
        assert self.orchestrator.cleanup_stats["total_images_removed"] == 3
        assert self.orchestrator.cleanup_stats["total_space_saved_bytes"] == 150 * 1024 * 1024
        assert self.orchestrator.cleanup_stats["last_cleanup_time"] is not None
        assert len(self.orchestrator.cleanup_stats["cleanup_operations"]) == 1

    def test_cleanup_statistics_reporting(self):
        """Test comprehensive cleanup statistics reporting."""
        # Set up some test data
        self.orchestrator._dynamic_images_created = {"biocage-auto:stat1", "biocage-auto:stat2"}
        self.orchestrator.cleanup_stats = {
            "total_images_removed": 5,
            "total_space_saved_bytes": 200 * 1024 * 1024,
            "last_cleanup_time": time.time() - 3600,  # 1 hour ago
            "cleanup_operations": [
                {
                    "timestamp": time.time() - 3600,
                    "policy": "age",
                    "result": {"removed_count": 2}
                }
            ]
        }
        
        # Mock image sizes
        self.mock_smart_image_manager._get_image_size.side_effect = [50 * 1024 * 1024, 75 * 1024 * 1024]
        self.mock_smart_image_manager.get_cache_info.return_value = {
            "total_cached_images": 3,
            "cache_entries": []
        }
        
        stats = self.orchestrator.get_cleanup_statistics()
        
        # Verify statistics structure
        assert "current_dynamic_images" in stats
        assert "cleanup_config" in stats
        assert "historical_stats" in stats
        assert "cache_info" in stats
        assert "system_info" in stats
        
        # Verify current dynamic images info
        current = stats["current_dynamic_images"]
        assert current["count"] == 2
        assert current["total_size_bytes"] == 125 * 1024 * 1024  # 50MB + 75MB
        
        # Verify cleanup config
        config = stats["cleanup_config"]
        assert config["policy"] == "combined"
        assert config["max_age_seconds"] == 3600
        assert config["max_count"] == 5
        
        # Verify historical stats
        historical = stats["historical_stats"]
        assert historical["total_images_removed"] == 5
        assert historical["total_space_saved_bytes"] == 200 * 1024 * 1024

    def test_dynamic_images_info(self):
        """Test dynamic images information reporting."""
        self.orchestrator._dynamic_images_created = {"biocage-auto:info1", "biocage-auto:info2"}
        
        # Mock image existence and sizes
        self.mock_smart_image_manager._image_exists.side_effect = [True, False]
        self.mock_smart_image_manager._get_image_size.side_effect = [25 * 1024 * 1024, 0]
        
        # Mock the fallback DockerClient and its methods
        with patch('biocage.container.docker_client.DockerClient') as mock_docker_class:
            mock_fallback_client = Mock()
            mock_docker_class.return_value = mock_fallback_client
            
            # Mock the orchestrator's private methods for fallback case
            with patch.object(self.orchestrator, '_image_exists', side_effect=[True, False]):
                with patch.object(self.orchestrator, '_get_image_size', side_effect=[25 * 1024 * 1024, 0]):
                    info = self.orchestrator.get_dynamic_images_info()
        
        # Verify info structure
        assert info["count"] == 2
        assert info["total_size_bytes"] == 25 * 1024 * 1024  # Only one image exists
        
        # Verify individual image info
        images = info["images"]
        assert len(images) == 2
        
        # First image should exist and have size
        img1 = next(img for img in images if img["name"] == "biocage-auto:info1")
        assert img1["exists"] is True
        assert img1["size_bytes"] == 25 * 1024 * 1024
        
        # Second image should not exist
        img2 = next(img for img in images if img["name"] == "biocage-auto:info2")
        assert img2["exists"] is False
        assert img2["size_bytes"] == 0

    def test_cleanup_policy_configuration(self):
        """Test cleanup policy configuration methods."""
        # Test initial configuration
        assert self.orchestrator.cleanup_policy == "combined"
        assert self.orchestrator.cleanup_max_age == 3600
        
        # Test policy reconfiguration
        self.orchestrator.configure_cleanup_policy(
            policy="age",
            max_age=7200,
            max_count=15,
            max_size_mb=200,
            exclude_patterns=["protected-*"]
        )
        
        assert self.orchestrator.cleanup_policy == "age"
        assert self.orchestrator.cleanup_max_age == 7200
        assert self.orchestrator.cleanup_max_count == 15
        assert self.orchestrator.cleanup_max_size_mb == 200
        assert "protected-*" in self.orchestrator.cleanup_exclude_patterns

    def test_cleanup_exclusion_management(self):
        """Test cleanup exclusion pattern management."""
        # Test adding exclusions
        self.orchestrator.add_cleanup_exclusion("important-image")
        self.orchestrator.add_cleanup_exclusion("production-*")
        
        assert "important-image" in self.orchestrator.cleanup_exclude_patterns
        assert "production-*" in self.orchestrator.cleanup_exclude_patterns
        
        # Test removing exclusions
        removed = self.orchestrator.remove_cleanup_exclusion("important-image")
        assert removed is True
        assert "important-image" not in self.orchestrator.cleanup_exclude_patterns
        
        # Test removing non-existent exclusion
        removed = self.orchestrator.remove_cleanup_exclusion("non-existent")
        assert removed is False

    def test_smart_image_manager_cache_synchronization(self):
        """Test cache synchronization with SmartImageManager."""
        # Set up mock cache with non-existent images
        self.mock_smart_image_manager.image_cache = {
            "fingerprint1": {"image_name": "biocage-auto:exists"},
            "fingerprint2": {"image_name": "biocage-auto:removed"}
        }
        
        # Mock image existence - one exists, one doesn't
        self.mock_docker_client.list_images.side_effect = [
            ["biocage-auto:exists"],  # First image exists
            []  # Second image doesn't exist
        ]
        
        self.orchestrator._sync_smart_image_manager_cache()
        
        # Verify that non-existent image was removed from cache
        assert "fingerprint1" in self.mock_smart_image_manager.image_cache
        assert "fingerprint2" not in self.mock_smart_image_manager.image_cache

    def test_cleanup_error_handling(self):
        """Test error handling during cleanup operations."""
        self.orchestrator._dynamic_images_created = {"biocage-auto:error-test"}
        
        # Mock various failures
        self.mock_docker_client.list_images.side_effect = Exception("Docker daemon not running")
        
        # Should not raise exception, should handle gracefully
        self.orchestrator._cleanup_dynamic_images()
        
        # Verify error was logged and handled
        # (In real test, we'd check log output, but here we just ensure no exception)

    def test_cleanup_without_smart_image_manager(self):
        """Test cleanup functionality when SmartImageManager is not available."""
        # Create orchestrator without smart image manager
        orchestrator = BioCageOrchestrator(
            auto_detect_dependencies=False,  # No SmartImageManager
            auto_cleanup_dynamic_images=True
        )
        
        orchestrator._dynamic_images_created = {"biocage-auto:basic-test"}
        
        # Mock docker client directly
        with patch('biocage.container.docker_client.DockerClient') as mock_docker_class:
            mock_client = Mock()
            mock_docker_class.return_value = mock_client
            mock_client.list_images.return_value = ["biocage-auto:basic-test"]
            mock_client.run_command.side_effect = [
                Mock(stdout="100MB"),  # Size check
                Mock(stdout=""),  # Container list
                Mock(stdout="Image removed")  # Removal
            ]
            
            with patch.object(orchestrator, '_get_image_size', return_value=100 * 1024 * 1024):
                with patch.object(orchestrator, '_image_exists', return_value=True):
                    orchestrator._cleanup_dynamic_images()
        
        # Verify cleanup was performed
        assert mock_client.run_command.called

    def test_format_bytes_utility(self):
        """Test byte formatting utility function."""
        assert self.orchestrator._format_bytes(500) == "500.0B"
        assert self.orchestrator._format_bytes(1536) == "1.5KB"
        assert self.orchestrator._format_bytes(1048576) == "1.0MB"
        assert self.orchestrator._format_bytes(1073741824) == "1.0GB"
        assert self.orchestrator._format_bytes(1099511627776) == "1.0TB"

    def test_format_age_utility(self):
        """Test age formatting utility function."""
        assert self.orchestrator._format_age(1800) == "30.0 minutes"  # 30 minutes
        assert self.orchestrator._format_age(7200) == "2.0 hours"     # 2 hours
        assert self.orchestrator._format_age(172800) == "2.0 days"   # 2 days

    def test_format_timestamp_utility(self):
        """Test timestamp formatting utility function."""
        assert self.orchestrator._format_timestamp(None) == "Never"
        
        # Test recent timestamp
        recent_time = time.time() - 30  # 30 seconds ago
        assert "30 seconds ago" in self.orchestrator._format_timestamp(recent_time)
        
        # Test older timestamp
        old_time = time.time() - 7200  # 2 hours ago
        assert "hours ago" in self.orchestrator._format_timestamp(old_time)

    @pytest.mark.parametrize("policy", ["age", "count", "size", "combined"])
    def test_different_cleanup_policies(self, policy):
        """Test different cleanup policies work correctly."""
        self.orchestrator.cleanup_policy = policy
        
        # Mock successful cleanup
        cleanup_result = {
            "removed_count": 2,
            "failed_count": 0,
            "space_saved_bytes": 100 * 1024 * 1024,
            "policy_used": policy
        }
        
        self.mock_smart_image_manager.cleanup_old_images.return_value = cleanup_result
        
        result = self.orchestrator.perform_smart_cleanup()
        
        # Verify policy was passed correctly
        call_args = self.mock_smart_image_manager.cleanup_old_images.call_args
        assert call_args[1]["policy"] == policy
        assert result["policy_used"] == policy

    def test_cleanup_with_exclusion_patterns(self):
        """Test that exclusion patterns are properly applied."""
        self.orchestrator.cleanup_exclude_patterns = ["important-*", "base-image"]
        
        # Mock cleanup
        self.mock_smart_image_manager.cleanup_old_images.return_value = {
            "removed_count": 1,
            "failed_count": 0,
            "space_saved_bytes": 50 * 1024 * 1024
        }
        
        self.orchestrator.perform_smart_cleanup()
        
        # Verify exclusion patterns were passed
        call_args = self.mock_smart_image_manager.cleanup_old_images.call_args
        assert call_args[1]["exclude_patterns"] == ["important-*", "base-image"]

    def test_cleanup_statistics_persistence(self):
        """Test that cleanup statistics persist across multiple operations."""
        # Initial cleanup
        self.mock_smart_image_manager.cleanup_old_images.return_value = {
            "removed_count": 2,
            "space_saved_bytes": 100 * 1024 * 1024
        }
        
        self.orchestrator.perform_smart_cleanup()
        assert self.orchestrator.cleanup_stats["total_images_removed"] == 2
        
        # Second cleanup
        self.mock_smart_image_manager.cleanup_old_images.return_value = {
            "removed_count": 3,
            "space_saved_bytes": 150 * 1024 * 1024
        }
        
        self.orchestrator.perform_smart_cleanup()
        assert self.orchestrator.cleanup_stats["total_images_removed"] == 5  # 2 + 3
        assert self.orchestrator.cleanup_stats["total_space_saved_bytes"] == 250 * 1024 * 1024  # 100MB + 150MB


class TestSmartImageManagerCleanup:
    """Test suite for SmartImageManager cleanup functionality."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_docker_client = Mock(spec=DockerClient)
        self.manager = SmartImageManager()
        self.manager.docker_client = self.mock_docker_client

    def test_cleanup_by_age_policy(self):
        """Test age-based cleanup policy."""
        # Set up cache with old and new entries
        current_time = time.time()
        self.manager.image_cache = {
            "old_fingerprint": {
                "image_name": "biocage-auto:old",
                "timestamp": current_time - 86400 * 8,  # 8 days ago
                "dependencies": {"numpy": "1.21.0"}
            },
            "new_fingerprint": {
                "image_name": "biocage-auto:new",
                "timestamp": current_time - 3600,  # 1 hour ago
                "dependencies": {"pandas": "1.3.0"}
            }
        }
        
        # Mock image operations
        self.mock_docker_client.list_images.return_value = ["biocage-auto:old", "biocage-auto:new"]
        self.mock_docker_client.run_command.side_effect = [
            Mock(stdout="200MB"),  # Old image size
            Mock(stdout=""),  # Container list
            Mock(stdout=""),  # Container removal
            Mock(stdout=""),  # Image removal
        ]
        
        with patch.object(self.manager, '_remove_image_with_cleanup', return_value=True):
            result = self.manager._cleanup_by_age(604800, [])  # 7 days max age
        
        # Verify only old image was removed
        assert result["removed_count"] == 1
        assert result["failed_count"] == 0
        assert "old_fingerprint" not in self.manager.image_cache
        assert "new_fingerprint" in self.manager.image_cache

    def test_cleanup_by_count_policy(self):
        """Test count-based cleanup policy."""
        # Set up cache with more images than allowed
        current_time = time.time()
        self.manager.image_cache = {
            "fingerprint1": {"image_name": "img1", "timestamp": current_time - 100},
            "fingerprint2": {"image_name": "img2", "timestamp": current_time - 200},
            "fingerprint3": {"image_name": "img3", "timestamp": current_time - 300},
            "fingerprint4": {"image_name": "img4", "timestamp": current_time - 400},
        }
        
        # Keep only 2 images, should remove 2 oldest
        with patch.object(self.manager, '_remove_image_with_cleanup', return_value=True):
            result = self.manager._cleanup_by_count(2, [])
        
        # Verify 2 images were removed
        assert result["removed_count"] == 2
        assert len(self.manager.image_cache) == 2

    def test_cleanup_by_size_policy(self):
        """Test size-based cleanup policy."""
        # Set up cache with images totaling more than limit
        self.manager.image_cache = {
            "fingerprint1": {"image_name": "img1", "timestamp": time.time() - 100},
            "fingerprint2": {"image_name": "img2", "timestamp": time.time() - 200},
        }
        
        # Mock image sizes (total 300MB, limit 200MB)
        self.mock_docker_client.run_command.side_effect = [
            Mock(stdout="150MB"),  # img1 size
            Mock(stdout="150MB"),  # img2 size
        ]
        
        with patch.object(self.manager, '_remove_image_with_cleanup', return_value=True):
            result = self.manager._cleanup_by_size(200, [])  # 200MB limit
        
        # Verify at least one image was removed
        assert result["removed_count"] >= 1

    def test_cleanup_with_exclusion_patterns(self):
        """Test cleanup with exclusion patterns."""
        current_time = time.time()
        self.manager.image_cache = {
            "important_fp": {"image_name": "important-image", "timestamp": current_time - 86400},
            "normal_fp": {"image_name": "normal-image", "timestamp": current_time - 86400},
        }
        
        # Mock both images exist
        self.mock_docker_client.list_images.return_value = ["important-image", "normal-image"]
        
        with patch.object(self.manager, '_remove_image_with_cleanup', return_value=True):
            with patch.object(self.manager, '_should_exclude_image', side_effect=[True, False]):  # important-image excluded, normal-image not
                result = self.manager._cleanup_by_age(3600, ["important-*"])  # 1 hour, exclude important
        
        # Verify only normal image was removed
        assert result["removed_count"] == 1
        assert "important_fp" in self.manager.image_cache
        assert "normal_fp" not in self.manager.image_cache

    def test_cleanup_error_handling(self):
        """Test cleanup error handling."""
        self.manager.image_cache = {
            "fingerprint1": {"image_name": "img1", "timestamp": time.time() - 86400},
        }
        
        # Mock image removal failure
        with patch.object(self.manager, '_remove_image_with_cleanup', return_value=False):
            result = self.manager._cleanup_by_age(3600, [])
        
        # Verify failure was recorded
        assert result["removed_count"] == 0
        assert result["failed_count"] == 1
        assert len(result["cleanup_details"]) == 1
        assert result["cleanup_details"][0]["failed"] is True


if __name__ == "__main__":
    pytest.main([__file__])
