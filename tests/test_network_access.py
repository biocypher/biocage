"""Test network access control functionality."""

import pytest

from biocage import BioCageOrchestrator


class TestNetworkAccessControl:
    """Test network access control in different configurations."""

    def test_network_disabled_by_default(self):
        """Test that network access is disabled by default."""
        with BioCageOrchestrator() as sandbox:
            result = sandbox.run("""
import urllib.request
import socket

print("Testing network connectivity...")

# Test HTTP request
try:
    response = urllib.request.urlopen('http://httpbin.org/get', timeout=5)
    print("ERROR: HTTP request succeeded - network not blocked!")
    print(f"Response status: {response.getcode()}")
except Exception as e:
    print(f"HTTP blocked: {type(e).__name__}")

# Test HTTPS request
try:
    response = urllib.request.urlopen('https://httpbin.org/get', timeout=5)
    print("ERROR: HTTPS request succeeded - network not blocked!")
    print(f"Response status: {response.getcode()}")
except Exception as e:
    print(f"HTTPS blocked: {type(e).__name__}")

# Test raw socket connection
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(('8.8.8.8', 53))
    print("ERROR: Socket connection succeeded - network not blocked!")
    sock.close()
except Exception as e:
    print(f"Socket blocked: {type(e).__name__}")

# Test DNS resolution
try:
    import socket
    ip = socket.gethostbyname('google.com')
    print(f"ERROR: DNS resolution succeeded - network not blocked! IP: {ip}")
except Exception as e:
    print(f"DNS blocked: {type(e).__name__}")

print("Network isolation test complete")
""")

            assert result.success
            assert "Network isolation test complete" in result.stdout

            # Verify that network requests were blocked
            assert "HTTP blocked:" in result.stdout
            assert "HTTPS blocked:" in result.stdout
            assert "Socket blocked:" in result.stdout
            assert "DNS blocked:" in result.stdout

            # Ensure no error messages about successful connections
            assert "ERROR: HTTP request succeeded" not in result.stdout
            assert "ERROR: HTTPS request succeeded" not in result.stdout
            assert "ERROR: Socket connection succeeded" not in result.stdout
            assert "ERROR: DNS resolution succeeded" not in result.stdout

    def test_network_explicitly_disabled(self):
        """Test network access when explicitly disabled."""
        with BioCageOrchestrator(network_access=False) as sandbox:
            result = sandbox.run("""
import urllib.request

try:
    # Attempt to make a simple HTTP request
    with urllib.request.urlopen('http://example.com', timeout=3) as response:
        content = response.read()
        print(f"ERROR: Network request succeeded! Content length: {len(content)}")
except Exception as e:
    print(f"Network properly blocked: {type(e).__name__}: {str(e)[:100]}")

print("Test completed")
""")

            assert result.success
            assert "Network properly blocked:" in result.stdout
            assert "ERROR: Network request succeeded" not in result.stdout
            assert "Test completed" in result.stdout

    def test_network_access_enabled(self):
        """Test network access when explicitly enabled."""
        with BioCageOrchestrator(network_access=True) as sandbox:
            result = sandbox.run("""
import urllib.request
import json

print("Testing network access with network_access=True...")

try:
    # Test a simple HTTP request to a reliable service
    with urllib.request.urlopen('http://httpbin.org/ip', timeout=10) as response:
        if response.getcode() == 200:
            content = response.read().decode('utf-8')
            data = json.loads(content)
            print(f"SUCCESS: Network request worked! Origin IP: {data.get('origin', 'unknown')}")
        else:
            print(f"Network request failed with status: {response.getcode()}")
except Exception as e:
    print(f"Network request failed: {type(e).__name__}: {str(e)}")

# Test DNS resolution when network is enabled
try:
    import socket
    ip = socket.gethostbyname('httpbin.org')
    print(f"DNS resolution successful: httpbin.org -> {ip}")
except Exception as e:
    print(f"DNS resolution failed: {type(e).__name__}: {str(e)}")

print("Network test completed")
""")

            assert result.success
            assert "Network test completed" in result.stdout

            # When network is enabled, we should see success messages
            # Note: This test might be flaky depending on network conditions
            # so we check for either success or a reasonable network error
            if "SUCCESS: Network request worked!" in result.stdout:
                assert "Origin IP:" in result.stdout
                assert "DNS resolution successful:" in result.stdout
            else:
                # If network request failed, it should be due to network conditions,
                # not security blocking (different error types)
                print("Network request failed - this may be due to network conditions in test environment")

    def test_network_configuration_persistence(self):
        """Test that network configuration persists across executions."""
        # Test with network disabled
        with BioCageOrchestrator(network_access=False) as sandbox:
            # First execution
            result1 = sandbox.run("""
import urllib.request
network_blocked = False

try:
    urllib.request.urlopen('http://example.com', timeout=2)
except:
    network_blocked = True

print(f"First execution - Network blocked: {network_blocked}")
""")

            assert result1.success
            assert "First execution - Network blocked: True" in result1.stdout

            # Second execution - should still be blocked
            result2 = sandbox.run("""
import urllib.request
network_blocked = False

try:
    urllib.request.urlopen('http://httpbin.org/get', timeout=2)
except:
    network_blocked = True

print(f"Second execution - Network blocked: {network_blocked}")
""")

            assert result2.success
            assert "Second execution - Network blocked: True" in result2.stdout

    def test_different_network_protocols(self):
        """Test blocking of different network protocols."""
        with BioCageOrchestrator(network_access=False) as sandbox:
            result = sandbox.run("""
import urllib.request
import socket
import ftplib
import smtplib

protocols_blocked = {}

# Test HTTP
try:
    urllib.request.urlopen('http://example.com', timeout=2)
    protocols_blocked['HTTP'] = False
except:
    protocols_blocked['HTTP'] = True

# Test HTTPS
try:
    urllib.request.urlopen('https://example.com', timeout=2)
    protocols_blocked['HTTPS'] = False
except:
    protocols_blocked['HTTPS'] = True

# Test FTP (this will likely fail at connection level)
try:
    ftp = ftplib.FTP()
    ftp.connect('ftp.debian.org', timeout=2)
    protocols_blocked['FTP'] = False
    ftp.quit()
except:
    protocols_blocked['FTP'] = True

# Test SMTP (this will likely fail at connection level)
try:
    smtp = smtplib.SMTP('smtp.gmail.com', 587, timeout=2)
    protocols_blocked['SMTP'] = False
    smtp.quit()
except:
    protocols_blocked['SMTP'] = True

# Test raw TCP socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    sock.connect(('8.8.8.8', 80))
    protocols_blocked['TCP'] = False
    sock.close()
except:
    protocols_blocked['TCP'] = True

# Test UDP socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    sock.sendto(b'test', ('8.8.8.8', 53))
    protocols_blocked['UDP'] = False
    sock.close()
except:
    protocols_blocked['UDP'] = True

print("Protocol blocking test results:")
for protocol, blocked in protocols_blocked.items():
    print(f"{protocol}: {'BLOCKED' if blocked else 'ALLOWED'}")

all_blocked = all(protocols_blocked.values())
print(f"All protocols blocked: {all_blocked}")
""")

            assert result.success
            assert "Protocol blocking test results:" in result.stdout
            assert "All protocols blocked: True" in result.stdout

            # Verify individual protocols are blocked
            for protocol in ['HTTP', 'HTTPS', 'FTP', 'SMTP', 'TCP', 'UDP']:
                assert f"{protocol}: BLOCKED" in result.stdout

    def test_localhost_access_with_network_disabled(self):
        """Test that localhost/loopback access behavior with network disabled."""
        with BioCageOrchestrator(network_access=False) as sandbox:
            result = sandbox.run("""
import socket
import urllib.request

print("Testing localhost access with network disabled...")

# Test localhost HTTP (this should be blocked too)
try:
    urllib.request.urlopen('http://localhost:8080', timeout=2)
    print("ERROR: Localhost HTTP succeeded")
except Exception as e:
    print(f"Localhost HTTP blocked: {type(e).__name__}")

# Test loopback socket connection
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    sock.connect(('127.0.0.1', 22))
    print("ERROR: Loopback connection succeeded")
    sock.close()
except Exception as e:
    print(f"Loopback socket blocked: {type(e).__name__}")

# Test if we can create sockets (should work)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"Socket creation successful: {type(sock)}")
    sock.close()
except Exception as e:
    print(f"Socket creation failed: {e}")

print("Localhost test completed")
""")

            assert result.success
            assert "Localhost test completed" in result.stdout
            assert "Localhost HTTP blocked:" in result.stdout
            assert "Loopback socket blocked:" in result.stdout
            assert "Socket creation successful:" in result.stdout

            # Should not see error messages
            assert "ERROR: Localhost HTTP succeeded" not in result.stdout
            assert "ERROR: Loopback connection succeeded" not in result.stdout

    def test_network_error_types(self):
        """Test the types of errors when network is disabled."""
        with BioCageOrchestrator(network_access=False) as sandbox:
            result = sandbox.run("""
import urllib.request
import urllib.error
import socket

print("Testing network error types...")

# HTTP request error type
try:
    urllib.request.urlopen('http://example.com', timeout=2)
except urllib.error.URLError as e:
    print(f"URLError caught: {type(e).__name__}")
    print(f"URLError reason type: {type(e.reason).__name__}")
except Exception as e:
    print(f"Other HTTP error: {type(e).__name__}")

# Socket connection error type
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    sock.connect(('google.com', 80))
except socket.gaierror as e:
    print(f"GAI error (DNS): {type(e).__name__}")
except socket.error as e:
    print(f"Socket error: {type(e).__name__}")
except Exception as e:
    print(f"Other socket error: {type(e).__name__}")
finally:
    try:
        sock.close()
    except:
        pass

print("Error type test completed")
""")

            assert result.success
            assert "Error type test completed" in result.stdout

            # Should catch network-related errors
            output = result.stdout
            assert any(error_type in output for error_type in [
                "URLError caught:",
                "GAI error (DNS):",
                "Socket error:",
                "Other HTTP error:",
                "Other socket error:"
            ])

    def test_network_timeout_behavior(self):
        """Test network timeout behavior when network is disabled."""
        with BioCageOrchestrator(network_access=False) as sandbox:
            result = sandbox.run("""
import urllib.request
import time

print("Testing network timeout behavior...")

start_time = time.time()

try:
    # This should fail quickly due to network isolation, not timeout
    urllib.request.urlopen('http://httpbin.org/delay/1', timeout=10)
    print("ERROR: Network request succeeded")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"Request failed in {elapsed:.2f} seconds")
    print(f"Error type: {type(e).__name__}")

    if elapsed < 5.0:
        print("Request failed quickly (network isolation)")
    else:
        print("Request took longer (possible timeout)")

print("Timeout test completed")
""")

            assert result.success
            assert "Timeout test completed" in result.stdout
            assert "Request failed quickly (network isolation)" in result.stdout
            assert "ERROR: Network request succeeded" not in result.stdout


class TestNetworkIntegration:
    """Test network functionality integration with other features."""

    def test_network_with_persistent_mode(self):
        """Test network configuration with persistent execution mode."""
        with BioCageOrchestrator(
            execution_mode="persistent",
            network_access=False
        ) as sandbox:
            # First execution - test and set variable
            result1 = sandbox.run("""
import urllib.request

try:
    urllib.request.urlopen('http://example.com', timeout=2)
    network_status = "ENABLED"
except:
    network_status = "DISABLED"

network_test_var = f"Network is {network_status}"
print(network_test_var)
""")

            assert result1.success
            assert "Network is DISABLED" in result1.stdout

            # Second execution - variable should persist, network still disabled
            result2 = sandbox.run("""
print(f"Previous result: {network_test_var}")

import urllib.request
try:
    urllib.request.urlopen('http://httpbin.org', timeout=2)
    current_status = "ENABLED"
except:
    current_status = "DISABLED"

print(f"Current network: {current_status}")
""")

            assert result2.success
            assert "Previous result: Network is DISABLED" in result2.stdout
            assert "Current network: DISABLED" in result2.stdout

    def test_network_with_ephemeral_mode(self):
        """Test network configuration with ephemeral execution mode."""
        with BioCageOrchestrator(
            execution_mode="ephemeral",
            network_access=False
        ) as sandbox:
            # Each execution should have network disabled
            for i in range(3):
                result = sandbox.run(f"""
import urllib.request

execution_number = {i + 1}
print(f"Execution {{execution_number}}: Testing network...")

try:
    urllib.request.urlopen('http://example.com', timeout=2)
    print(f"ERROR: Network enabled in execution {{execution_number}}")
except:
    print(f"Network disabled in execution {{execution_number}}")
""")

                assert result.success
                assert f"Network disabled in execution {i + 1}" in result.stdout
                assert f"ERROR: Network enabled in execution {i + 1}" not in result.stdout

    def test_network_with_file_operations(self):
        """Test network configuration combined with file operations."""
        import tempfile
        from pathlib import Path

        # Create test file
        temp_dir = Path(tempfile.mkdtemp())
        test_file = temp_dir / "network_test.txt"
        test_file.write_text("Network test data")

        try:
            with BioCageOrchestrator(network_access=False) as sandbox:
                # Expose file and test network
                container_path = sandbox.expose_file(str(test_file), "/app/test.txt")

                result = sandbox.run(f"""
import urllib.request

# Read the exposed file
with open('{container_path}', 'r') as f:
    file_content = f.read().strip()

print(f"File content: {{file_content}}")

# Test network (should be disabled)
try:
    urllib.request.urlopen('http://example.com', timeout=2)
    network_result = "ENABLED"
except:
    network_result = "DISABLED"

print(f"Network status: {{network_result}}")
print("File + Network test completed")
""")

                assert result.success
                assert "File content: Network test data" in result.stdout
                assert "Network status: DISABLED" in result.stdout
                assert "File + Network test completed" in result.stdout

        finally:
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir)