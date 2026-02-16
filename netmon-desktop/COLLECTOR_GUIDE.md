# NetMon Collector Configuration

## Default Behavior (Production)

NetMon now uses **PingCollector** by default for real ICMP ping measurements:

```bash
python -m netmon
```

This will:
- Execute real system `ping` commands
- Display actual network latency measurements
- Show packet loss for unreachable hosts
- Timeout after 1000ms (1 second)

## Fallback to Fake Data

If PingCollector fails (import error, initialization error, or ping unavailable), the application automatically falls back to FakeCollectorAdapter with a clear warning in the status label.

## Environment Variable Override

Force use of simulated data for testing/development:

```bash
# Windows PowerShell
$env:NETMON_COLLECTOR="fake"
python -m netmon

# Windows CMD
set NETMON_COLLECTOR=fake
python -m netmon

# Linux/macOS
NETMON_COLLECTOR=fake python -m netmon
```

## Collector Comparison

| Feature | PingCollector | FakeCollectorAdapter |
|---------|--------------|---------------------|
| Data Source | Real ICMP ping | Simulated with randomness |
| Network Required | Yes | No (offline safe) |
| Privileges | May require admin/root | None |
| Localization | English ping output only | Language-independent |
| Performance | Network-dependent | Instant |
| Use Case | Production monitoring | Testing, demos, development |

## Status Messages

The status label shows the current collector state:

- **"Status: Ready"** - PingCollector successfully initialized
- **"Status: Using simulated data (NETMON_COLLECTOR=fake)"** - Explicitly using fake data
- **"Status: PingCollector unavailable (import): ..."** - Import failed, using fake data
- **"Status: PingCollector initialization failed: ..."** - Runtime error, using fake data

## Troubleshooting

**Problem**: All pings show as packet loss
- **Cause**: Non-English Windows (see PingCollector localization limitation)
- **Solution**: Use `NETMON_COLLECTOR=fake` or set system locale to English

**Problem**: "PingCollector unavailable (import)"
- **Cause**: Missing implementation file or import error
- **Solution**: Check that `netmon/collector_ping.py` exists

**Problem**: "PingCollector initialization failed"
- **Cause**: Invalid timeout parameter or system configuration
- **Solution**: Check system permissions and network configuration

## Architecture

The collector selection happens at application startup in `netmon/__main__.py`:

1. Check `NETMON_COLLECTOR` environment variable
2. If not "fake", try to import and instantiate PingCollector
3. On any failure, fall back to FakeCollectorAdapter
4. Pass selected collector to MainWindow (collector-agnostic)
5. Show warning in status label if fallback occurred

This design ensures:
- **Resilience**: Application always starts, even if ping unavailable
- **Transparency**: User sees clear status about data source
- **Flexibility**: Easy to switch between real and fake data
- **Maintainability**: MainWindow remains decoupled from collector choice
