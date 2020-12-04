import numpy as np
import pandas as pd
import pathlib
from opentimspy.opentims import OpenTIMS, all_columns

from .sql import tables_names, table2df


class TimsPyDF(OpenTIMS):
    """TimsData that uses info about Frames."""
    def __init__(self, analysis_directory):
        """Create an instance of the TimsPyDF.

        Args:
            analysis_directory (str, unicode string): path to the folder containing 'analysis.tdf' and 'analysis.tdf_raw'.
        """
        super().__init__(analysis_directory)
        self.analysis_directory = pathlib.Path(analysis_directory)
        self.frames = self.table2df("frames").sort_values('Id')
        self.frames_no = self.max_frame-self.min_frame+1
        self._ms1_mask = np.zeros(self.frames_no,
                                  dtype=bool)
        self._ms1_mask[self.ms1_frames-1] = True
        self.rt = self.frames.Time.values


    def tables_names(self):
        """List names of tables in the SQLite db.

        Returns:
            pd.DataTable: table with names of tables one can get with 'table2df'.
        """
        return tables_names(self.analysis_directory/'analysis.tdf')


    def table2df(self, name):
        """Retrieve a table with SQLite connection from a data base.

        Args:
            name (str): Name of the table to extract.
        Returns:
            pd.DataFrame: required data frame.
        """
        return table2df(self.analysis_directory/'analysis.tdf', name)

 
    def __repr__(self):
        return f"{self.__class__.__name__}({self.peaks_cnt} peaks)"


    def summary(self):
        """Print a short summary of the data content.

        Includes the number of peaks, the minimal and the maximal frame numbers.
        """
        print(f"Peaks Inside:   {self.peaks_cnt}")
        print(f"Minimal Frame:  {self.min_frame}")
        print(f"Maximal Frame:  {self.max_frame}")


    def query(self, frames, columns=all_columns):
        """Get data from a selection of frames.

        Args:
            frames (int, iterable): Frames to choose. Passing an integer results in extracting that one frame.
            columns (tuple): which columns to extract? Defaults to all possible columns.
        Returns:
            pd.DataFrame: Data frame filled with columns with raw data.
        """
        return pd.DataFrame(super().query(frames, columns))


    def plot_peak_counts(self, show=True):
        """Plot peak counts per frame.

        Arguments:
            show (bool): Show the plot immediately, or just add it to the canvas.
        """
        import matplotlib.pyplot as plt
        MS1 = self._ms1_mask
        NP = self.frames.NumPeaks
        plt.plot(self.rt[ MS1], NP[ MS1], label="MS1")
        plt.plot(self.rt[~MS1], NP[~MS1], label="MS2")
        plt.legend()
        plt.xlabel("Retention Time")
        plt.ylabel("Number of Peaks")
        plt.title("Peak Counts per Frame")
        if show:
            plt.show()


    def intensity_per_frame(self, recalibrated=True):
        """Get sum of intensity per each frame (dt).

        Arguments:
            recalibrated (bool): Use Bruker recalibrated total intensities or calculate them from scratch with OpenTIMS?
        
        Returns:
            np.array: sums of intensities per frame. 
        """
        return self.frames.SummedIntensities if recalibrated else self.framesTIC()


    def plot_TIC(self, recalibrated=True, show=True):
        """Plot peak counts per frame.

        Arguments:
            recalibrated (bool): Use Bruker recalibrated total intensities or calculate them from scratch with OpenTIMS?
            show (bool): Show the plot immediately, or just add it to the canvas?
        """
        import matplotlib.pyplot as plt
        MS1 = self._ms1_mask
        I = self.intensity_per_frame(recalibrated)
        plt.plot(self.rt[ MS1], I[ MS1], label="MS1")
        plt.plot(self.rt[~MS1], I[~MS1], label="MS2")
        plt.legend()
        plt.xlabel("Retention Time")
        plt.ylabel("Intensity")
        plt.title("Total Intensity [Ion Current]")
        if show:
            plt.show()


    #TODO: this should be reimplemented later on in C++, single core...
    def intensity_given_mz_dt(self,
                              frames=None,
                              mz_bin_borders=np.linspace(500, 2500, 1001),
                              dt_bin_borders=np.linspace(0.8, 1.7, 101)):
        """Sum intensity over m/z-drift time rectangles.

        Typically it does not make too much sense to mix MS1 intensities with the others here.

        Arguments:
            frames (iterable): Frames to consider. Defaults to all ms1_frames. 
            mz_bin_borders (np.array): Positions of bin borders for mass over charge ratios.
            dt_bin_borders (np.array): Positions of bin borders for drift times.
        Returns:
            tuple: np.array with intensities, the positions of bin borders for mass over charge ratios and drift times.
        """
        if frames is None:
            frames = self.ms1_frames

        I = np.zeros(shape=(len(mz_bin_borders)-1,
                            len(dt_bin_borders)-1),
                     dtype=float)
        # float because numpy does not have histogram2d with ints 

        for X in self.query_iter(frames=frames,
                                 columns=('mz','dt','intensity')):
            I_fr, _,_ = np.histogram2d(X.mz, X.dt,
                                       bins=[mz_bin_borders,
                                             dt_bin_borders], 
                                       weights=X.intensity)
            I += I_fr

        return I, mz_bin_borders, dt_bin_borders


    def plot_intensity_given_mz_dt(self, 
                                   intensity_transformation=np.sqrt,
                                   show=True,
                                   imshow_kwds={'interpolation':'nearest',
                                                'aspect':'auto'},
                                   **kwds):
        """Sum intensity over m/z-drift time rectangles.

        Plot a transformation of the sum of intensities.
        Usually, plotting the square root of summed intensities looks best.


        Arguments:
            intensity_transformation (np.ufunc): Function that transforms intensities. Default to square root.
            show (bool): Show the plot immediately, or just add it to the canvas?
            **kwds: Keyword arguments for the 'intensity_given_mz_dt' method.
        """
        import matplotlib.pyplot as plt
        
        I, mz_bin_borders, dt_bin_borders = self.intensity_given_mz_dt(**kwds)
        plt.imshow(intensity_transformation(I),
                   extent=[mz_bin_borders[0], mz_bin_borders[-1],
                           dt_bin_borders[0], dt_bin_borders[-1]],
                   **imshow_kwds)
        plt.xlabel("Mass / Charge")
        plt.ylabel("Drift Time")
        plt.title("Total Intensity")
        if show:
            plt.show()