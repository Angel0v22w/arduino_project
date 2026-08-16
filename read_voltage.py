#!/usr/bin/env python3
"""Read and plot two voltage channels from Arduino/Wokwi."""

from __future__ import annotations

import argparse
import csv
from collections import deque
from dataclasses import dataclass
import math
from pathlib import Path
from queue import Empty, Queue
import sys
from threading import Event, Thread
import time
from typing import Iterable, Iterator, TextIO


@dataclass(frozen=True, slots=True)
class VoltageSample:
    """One received pair of voltage measurements."""

    elapsed_s: float
    u1_v: float
    u2_v: float


@dataclass(frozen=True, slots=True)
class SourceFailure:
    """Transfers a source exception from the worker to the main thread."""

    error: Exception


END_OF_SOURCE = object()
QueueItem = VoltageSample | SourceFailure | object


def parse_voltage_line(line: str, elapsed_s: float = 0.0) -> VoltageSample | None:
    """Parse ``U1,U2`` in volts; ignore blank lines and comments."""

    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    fields = [field.strip() for field in stripped.split(",")]
    if len(fields) != 2:
        raise ValueError(f"expected 2 comma-separated values, got {len(fields)}")

    try:
        u1_v, u2_v = (float(field) for field in fields)
    except ValueError as exc:
        raise ValueError("both fields must be numbers") from exc

    if not (math.isfinite(u1_v) and math.isfinite(u2_v)):
        raise ValueError("voltage values must be finite")

    return VoltageSample(elapsed_s=elapsed_s, u1_v=u1_v, u2_v=u2_v)


def serial_samples(
    url: str, baudrate: int, stop_event: Event
) -> Iterator[VoltageSample]:
    """Yield voltage pairs from a physical or RFC2217 serial port."""

    try:
        import serial
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Липсва pyserial. Изпълни: python -m pip install -r requirements.txt"
        ) from exc

    started_at = time.monotonic()
    with serial.serial_for_url(url, baudrate=baudrate, timeout=0.25) as port:
        print(f"Свързано към {url} @ {baudrate} baud.")

        while not stop_event.is_set():
            raw_line = port.readline()
            if not raw_line:
                continue

            line = raw_line.decode("utf-8", errors="replace")
            elapsed_s = time.monotonic() - started_at
            try:
                sample = parse_voltage_line(line, elapsed_s)
            except ValueError as exc:
                print(
                    f"Пропуснат невалиден ред {line.strip()!r}: {exc}",
                    file=sys.stderr,
                )
                continue

            if sample is not None:
                yield sample


def demo_samples(stop_event: Event, rate_hz: float = 10.0) -> Iterator[VoltageSample]:
    """Generate deterministic test voltages without Arduino or Wokwi."""

    started_at = time.monotonic()
    interval_s = 1.0 / rate_hz
    next_sample_at = started_at
    print("Демонстрационен режим: генерират се две тестови напрежения.")

    while not stop_event.is_set():
        now = time.monotonic()
        if now < next_sample_at:
            stop_event.wait(next_sample_at - now)
            continue

        elapsed_s = now - started_at
        yield VoltageSample(
            elapsed_s=elapsed_s,
            u1_v=2.5 + 2.1 * math.sin(2.0 * math.pi * elapsed_s / 8.0),
            u2_v=2.5 + 1.7 * math.sin(2.0 * math.pi * elapsed_s / 5.0 + 0.8),
        )
        next_sample_at += interval_s


class CsvLogger:
    """Optional on-disk log of all displayed samples."""

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._file: TextIO | None = None
        self._writer: csv.writer | None = None

    def __enter__(self) -> CsvLogger:
        if self._path is not None:
            self._file = self._path.open("w", encoding="utf-8", newline="")
            self._writer = csv.writer(self._file)
            self._writer.writerow(("elapsed_s", "u1_v", "u2_v"))
        return self

    def write(self, sample: VoltageSample) -> None:
        if self._writer is None or self._file is None:
            return
        self._writer.writerow(
            (f"{sample.elapsed_s:.3f}", f"{sample.u1_v:.3f}", f"{sample.u2_v:.3f}")
        )
        self._file.flush()

    def __exit__(self, *_: object) -> None:
        if self._file is not None:
            self._file.close()


def pump_samples(
    source: Iterable[VoltageSample], inbox: Queue[QueueItem], stop_event: Event
) -> None:
    """Read a potentially blocking source without freezing the plot window."""

    try:
        for sample in source:
            if stop_event.is_set():
                break
            inbox.put(sample)
    except Exception as exc:  # The main thread reports connection/dependency errors.
        inbox.put(SourceFailure(exc))
    finally:
        inbox.put(END_OF_SOURCE)


def run_console(
    inbox: Queue[QueueItem], logger: CsvLogger, stop_event: Event
) -> Exception | None:
    """Print samples until interrupted or the source stops."""

    while not stop_event.is_set():
        item = inbox.get()
        if item is END_OF_SOURCE:
            return None
        if isinstance(item, SourceFailure):
            return item.error
        if isinstance(item, VoltageSample):
            logger.write(item)
            print(f"U1 = {item.u1_v:.3f} V | U2 = {item.u2_v:.3f} V")
    return None


def run_plot(
    inbox: Queue[QueueItem],
    logger: CsvLogger,
    stop_event: Event,
    window_s: float,
) -> Exception | None:
    """Display a scrolling plot and return a source error, if one occurred."""

    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
    except ModuleNotFoundError as exc:
        return RuntimeError(
            "Липсва matplotlib. Изпълни: python -m pip install -r requirements.txt"
        )

    times: deque[float] = deque()
    values_u1: deque[float] = deque()
    values_u2: deque[float] = deque()
    source_error: list[Exception] = []

    figure, axis = plt.subplots()
    (line_u1,) = axis.plot([], [], label="U1 (A0)", color="tab:green")
    (line_u2,) = axis.plot([], [], label="U2 (A1)", color="tab:blue")
    latest_text = axis.text(
        0.02, 0.96, "Очакване на данни…", transform=axis.transAxes, va="top"
    )
    axis.set_title("Двусистемно измерване на напрежение")
    axis.set_xlabel("Време, s")
    axis.set_ylabel("Напрежение, V")
    axis.set_xlim(0.0, window_s)
    axis.set_ylim(0.0, 5.1)
    axis.grid(True, alpha=0.3)
    axis.legend(loc="upper right")
    figure.tight_layout()

    def update(_: int) -> tuple[object, object, object]:
        while True:
            try:
                item = inbox.get_nowait()
            except Empty:
                break

            if item is END_OF_SOURCE:
                if source_error:
                    plt.close(figure)
                continue
            if isinstance(item, SourceFailure):
                source_error.append(item.error)
                continue
            if not isinstance(item, VoltageSample):
                continue

            logger.write(item)
            times.append(item.elapsed_s)
            values_u1.append(item.u1_v)
            values_u2.append(item.u2_v)
            latest_text.set_text(
                f"U1 = {item.u1_v:.3f} V\nU2 = {item.u2_v:.3f} V"
            )

        if times:
            newest = times[-1]
            cutoff = newest - window_s
            while times and times[0] < cutoff:
                times.popleft()
                values_u1.popleft()
                values_u2.popleft()

            line_u1.set_data(times, values_u1)
            line_u2.set_data(times, values_u2)
            axis.set_xlim(max(0.0, newest - window_s), max(window_s, newest))

        return line_u1, line_u2, latest_text

    # Keep a live reference: matplotlib otherwise may garbage-collect the animation.
    animation = FuncAnimation(
        figure, update, interval=50, blit=False, cache_frame_data=False
    )
    _ = animation
    plt.show()
    stop_event.set()
    return source_error[0] if source_error else None


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Чете U1,U2 от Arduino/Wokwi и ги визуализира."
    )
    parser.add_argument(
        "--url",
        default="rfc2217://localhost:4000",
        help="Serial порт или URL (по подразбиране: %(default)s)",
    )
    parser.add_argument(
        "--baudrate", type=int, default=115200, help="Serial скорост (default: %(default)s)"
    )
    parser.add_argument(
        "--window",
        type=float,
        default=20.0,
        help="Ширина на графиката в секунди (default: %(default)s)",
    )
    parser.add_argument(
        "--csv", type=Path, help="По желание записва измерванията в CSV файл"
    )
    parser.add_argument(
        "--no-plot", action="store_true", help="Показва стойностите само в терминала"
    )
    parser.add_argument(
        "--demo", action="store_true", help="Генерира тестови данни без Arduino/Wokwi"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    if args.window <= 0:
        print("Грешка: --window трябва да бъде положително число.", file=sys.stderr)
        return 2
    if args.baudrate <= 0:
        print("Грешка: --baudrate трябва да бъде положително число.", file=sys.stderr)
        return 2

    stop_event = Event()
    inbox: Queue[QueueItem] = Queue()
    source = (
        demo_samples(stop_event)
        if args.demo
        else serial_samples(args.url, args.baudrate, stop_event)
    )
    worker = Thread(
        target=pump_samples,
        args=(source, inbox, stop_event),
        name="voltage-source",
        daemon=True,
    )
    worker.start()

    error: Exception | None = None
    try:
        with CsvLogger(args.csv) as logger:
            if args.no_plot:
                error = run_console(inbox, logger, stop_event)
            else:
                error = run_plot(inbox, logger, stop_event, args.window)
    except KeyboardInterrupt:
        print("\nИзмерването е спряно.")
    except OSError as exc:
        error = exc
    finally:
        stop_event.set()
        worker.join(timeout=1.0)

    if error is not None:
        print(f"Грешка: {error}", file=sys.stderr)
        if not args.demo:
            print(
                "Провери дали Wokwi симулацията работи и порт 4000 е свободен.",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

