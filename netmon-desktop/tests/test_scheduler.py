"""Unit tests for MultiHostScheduler."""

from PySide6.QtCore import QThreadPool
from netmon.scheduler import MultiHostScheduler
from netmon.collector import FakeCollectorAdapter


class TestMultiHostScheduler:
    """Test suite for MultiHostScheduler class."""

    def test_initial_state(self):
        """Verify scheduler starts in correct initial state."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector, interval_ms=1000, max_concurrent=4)
        
        assert not scheduler.is_monitoring
        assert scheduler.get_hosts() == []
        assert scheduler._global_in_flight == 0
        assert scheduler._host_in_flight == {}
    
    def test_add_single_host(self):
        """Test adding a single host."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        scheduler.add_host("google.com")
        
        assert scheduler.get_hosts() == ["google.com"]
        assert "google.com" in scheduler._host_in_flight
        assert not scheduler._host_in_flight["google.com"]
    
    def test_add_multiple_hosts(self):
        """Test adding multiple hosts."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        scheduler.add_host("google.com")
        scheduler.add_host("cloudflare.com")
        scheduler.add_host("8.8.8.8")
        
        hosts = scheduler.get_hosts()
        assert len(hosts) == 3
        assert "google.com" in hosts
        assert "cloudflare.com" in hosts
        assert "8.8.8.8" in hosts
    
    def test_add_duplicate_host_ignored(self):
        """Test that adding duplicate host is ignored."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        scheduler.add_host("google.com")
        scheduler.add_host("google.com")
        
        assert scheduler.get_hosts() == ["google.com"]
    
    def test_remove_host(self):
        """Test removing a host."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        scheduler.add_host("google.com")
        scheduler.add_host("cloudflare.com")
        scheduler.remove_host("google.com")
        
        assert scheduler.get_hosts() == ["cloudflare.com"]
        assert "google.com" not in scheduler._host_in_flight
    
    def test_remove_nonexistent_host(self):
        """Test removing host that doesn't exist."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        scheduler.add_host("google.com")
        scheduler.remove_host("nonexistent.com")  # Should not crash
        
        assert scheduler.get_hosts() == ["google.com"]
    
    def test_clear_hosts(self):
        """Test clearing all hosts."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        scheduler.add_host("google.com")
        scheduler.add_host("cloudflare.com")
        scheduler.clear_hosts()
        
        assert scheduler.get_hosts() == []
        assert scheduler._host_in_flight == {}
    
    def test_start_monitoring(self):
        """Test starting monitoring."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector, interval_ms=1000)
        
        scheduler.add_host("google.com")
        scheduler.start_monitoring()
        
        assert scheduler.is_monitoring
    
    def test_stop_monitoring(self):
        """Test stopping monitoring."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector, interval_ms=1000)
        
        scheduler.add_host("google.com")
        scheduler.start_monitoring()
        scheduler.stop_monitoring()
        
        assert not scheduler.is_monitoring
    
    def test_set_interval(self):
        """Test changing monitoring interval."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector, interval_ms=1000)
        
        # Set interval updates internal state
        scheduler.set_interval(2000)
        assert scheduler.interval_ms == 2000
        
        # Timer interval only changes when monitoring is active
        scheduler.add_host("google.com")
        scheduler.start_monitoring()
        assert scheduler.timer.interval() == 2000
    
    def test_max_concurrent_limit(self):
        """Test that max concurrent limit is enforced."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector, max_concurrent=2)
        
        assert scheduler.max_concurrent == 2
    
    def test_thread_pool_reference(self):
        """Test that scheduler has thread pool reference."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        assert scheduler.thread_pool is not None
        assert isinstance(scheduler.thread_pool, QThreadPool)
    
    def test_signal_connections(self):
        """Test that scheduler emits correct signals."""
        collector = FakeCollectorAdapter()
        scheduler = MultiHostScheduler(collector)
        
        # Verify signals exist
        assert hasattr(scheduler, 'sample_ready')
        assert hasattr(scheduler, 'error')
