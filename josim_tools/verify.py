""" Verify if a circuit works """

from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import numpy as np
import attr

from .formats import SpecFile
from .simulation import CircuitSimulator, CircuitSimulatorOutput, PlotParameter
from .configuration import VerifyConfiguration


@attr.s(auto_attribs=True, frozen=True, slots=True)
class VerifierResult:
    """ The result of a verification with optional additional information """

    succeed: bool
    failure_time: Optional[float] = None
    failure_point: Optional[List[int]] = None

    def __bool__(self) -> bool:
        """ Transforms the value into a boolean """
        return self.succeed


class Verifier:
    """ Verify that a circuit works given a spec file """

    simulator_: CircuitSimulator
    spec_file_: SpecFile
    threshold_: float
    wrspice_compatibility: bool = False

    def __init__(self, configuration: VerifyConfiguration):
        assert configuration.method == "spec_file"

        self.simulator_ = CircuitSimulator(
            configuration.circuit_path,
            [],
            wrspice_compatibility=configuration.wrspice_compatibility,
        )
        self.spec_file_ = SpecFile(configuration.file_path)
        self.threshold_ = configuration.threshold

        # Set traces to be in the right order
        names: List[str] = self.spec_file_.names()
        plot_parameters = [PlotParameter(name) for name in names]
        self.simulator_.change_traces(plot_parameters)

    def _simulate(self, params: Dict[str, float]) -> CircuitSimulatorOutput:
        parameters: List[str] = []
        values: List[float] = []

        for key, value in params.items():
            parameters.append(key)
            values.append(value)

        self.simulator_.change_parameters(parameters)
        return self.simulator_.simulate(values)

    def verify(self, params: Optional[Dict[str, float]] = None) -> VerifierResult:
        """ Verify if the set of parameters works """

        # Manage default parameters
        if params is None:
            params = {}

        # Simulate
        output = self._simulate(params)

        time_steps = np.array(self.spec_file_.time())
        phase_flips = np.array(self.spec_file_.data())

        # Calibration
        calibration_phase_flips = np.array(phase_flips[0])
        calibration_samples = np.array(output.sample(time_steps[0]))

        num_steps = time_steps.shape[0]

        for index in range(1, num_steps):
            time_step = time_steps[index]

            samples = np.array(output.sample(float(time_step)))

            phase_flips_sampled = (samples - calibration_samples) / (2 * np.pi)
            phase_flips_compare = phase_flips[index] - calibration_phase_flips

            difference = np.abs(phase_flips_sampled - phase_flips_compare)

            comparisons = difference > self.threshold_

            if np.any(comparisons):
                return VerifierResult(
                    False, float(time_step), list(np.where(comparisons)[0])
                )

        return VerifierResult(True)

    def plot(self, params: Optional[Dict[str, float]] = None) -> None:
        """ Plot the results and times the circuit is being checked """

        # Manage default parameters
        if params is None:
            params = {}

        output = self._simulate(params)

        plt.figure()

        # Plot vertical lines
        for sample_time in self.spec_file_.time():
            plt.axvline(float(sample_time))

        # Plot traces
        time_steps = output.time_steps
        for trace in output.traces:
            plt.plot(time_steps, trace.get_data(), label=trace.name)

        # Finish plot
        plt.legend()
        plt.show()
