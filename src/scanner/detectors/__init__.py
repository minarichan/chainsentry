"""Detector interface. Each detector maps a Contract to zero or more Findings."""

from __future__ import annotations

from abc import ABC, abstractmethod

from scanner.models import Contract, Finding


class Detector(ABC):
    id: str
    title: str

    @abstractmethod
    def detect(self, contract: Contract) -> list[Finding]:
        raise NotImplementedError


def all_detectors() -> list[Detector]:
    from scanner.detectors.access_control import AccessControlDetector
    from scanner.detectors.delegatecall import DelegateCallDetector
    from scanner.detectors.erc20_return import Erc20ReturnDetector
    from scanner.detectors.initializer import InitializerDetector
    from scanner.detectors.randomness import RandomnessDetector
    from scanner.detectors.reentrancy import (
        CrossFunctionReentrancyDetector,
        ReentrancyDetector,
    )
    from scanner.detectors.selfdestruct import SelfdestructDetector
    from scanner.detectors.timestamp import TimestampDetector
    from scanner.detectors.transfer_from import ArbitraryTransferFromDetector
    from scanner.detectors.tx_origin import TxOriginDetector
    from scanner.detectors.unchecked_calls import UncheckedCallsDetector

    return [
        ReentrancyDetector(),
        CrossFunctionReentrancyDetector(),
        AccessControlDetector(),
        TxOriginDetector(),
        UncheckedCallsDetector(),
        DelegateCallDetector(),
        SelfdestructDetector(),
        TimestampDetector(),
        RandomnessDetector(),
        Erc20ReturnDetector(),
        InitializerDetector(),
        ArbitraryTransferFromDetector(),
    ]
