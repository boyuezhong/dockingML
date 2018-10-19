# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
import sklearn
from sklearn import decomposition
from mdanaly import cmap
from mdanaly import gmxcli
import mdtraj as mt

class tSNE(object):

    def __init__(self):
        pass

    def Hbeta(self, D=np.array([]), beta=1.0):
        """
        Compute the perplexity and the P-row for a specific value of the
        precision of a Gaussian distribution.

        Parameters
        ----------
        D: numpy ndarray,

        beta: float,


        Returns
        -------
        H:
        P:
        """

        # Compute P-row and corresponding perplexity
        P = np.exp(-D.copy() * beta)
        sumP = sum(P)
        H = np.log(sumP) + beta * np.sum(D * P) / sumP
        P = P / sumP
        return H, P

    def x2p(self, X=np.array([]), tol=1e-5, perplexity=30.0):
        """
        Performs a binary search to get P-values in such a way that each
        conditional Gaussian has the same perplexity.

        Parameters
        ----------
        X
        tol
        perplexity

        Returns
        -------

        """

        # Initialize some variables
        print("Computing pairwise distances...")
        (n, d) = X.shape
        sum_X = np.sum(np.square(X), 1)
        D = np.add(np.add(-2 * np.dot(X, X.T), sum_X).T, sum_X)
        P = np.zeros((n, n))
        beta = np.ones((n, 1))
        logU = np.log(perplexity)

        # Loop over all datapoints
        for i in range(n):

            # Print progress
            if i % 500 == 0:
                print("Computing P-values for point %d of %d..." % (i, n))

            # Compute the Gaussian kernel and entropy for the current precision
            betamin = -np.inf
            betamax = np.inf
            Di = D[i, np.concatenate((np.r_[0:i], np.r_[i+1:n]))]
            (H, thisP) = self.Hbeta(Di, beta[i])

            # Evaluate whether the perplexity is within tolerance
            Hdiff = H - logU
            tries = 0
            while np.abs(Hdiff) > tol and tries < 50:

                # If not, increase or decrease precision
                if Hdiff > 0:
                    betamin = beta[i].copy()
                    if betamax == np.inf or betamax == -np.inf:
                        beta[i] = beta[i] * 2.
                    else:
                        beta[i] = (beta[i] + betamax) / 2.
                else:
                    betamax = beta[i].copy()
                    if betamin == np.inf or betamin == -np.inf:
                        beta[i] = beta[i] / 2.
                    else:
                        beta[i] = (beta[i] + betamin) / 2.

                # Recompute the values
                (H, thisP) = self.Hbeta(Di, beta[i])
                Hdiff = H - logU
                tries += 1

            # Set the final row of P
            P[i, np.concatenate((np.r_[0:i], np.r_[i+1:n]))] = thisP

        # Return final P-matrix
        print("Mean value of sigma: %f" % np.mean(np.sqrt(1 / beta)))
        return P

    def pca(self, X=np.array([]), no_dims=50):
        """
        Runs PCA on the NxD array X in order to reduce its dimensionality to
        no_dims dimensions.

        Parameters
        ----------
        X
        no_dims

        Returns
        -------

        """

        print("Preprocessing the data using PCA...")
        (n, d) = X.shape
        X = X - np.tile(np.mean(X, 0), (n, 1))
        (l, M) = np.linalg.eig(np.dot(X.T, X))
        Y = np.dot(X, M[:, 0:no_dims])
        return Y

    def tsne(self, X=np.array([]), no_dims=2, initial_dims=50, perplexity=30.0):
        """
        Runs t-SNE on the dataset in the NxD array X to reduce its
        dimensionality to no_dims dimensions. The syntaxis of the function is
        `Y = tsne.tsne(X, no_dims, perplexity), where X is an NxD NumPy array.

        Parameters
        ----------
        X
        no_dims
        initial_dims
        perplexity

        Returns
        -------

        """

        # Check inputs
        if isinstance(no_dims, float):
            print("Error: array X should have type float.")
            return -1
        if round(no_dims) != no_dims:
            print("Error: number of dimensions should be an integer.")
            return -1

        # Initialize variables
        X = self.pca(X, initial_dims).real
        (n, d) = X.shape
        max_iter = 1000
        initial_momentum = 0.5
        final_momentum = 0.8
        eta = 500
        min_gain = 0.01
        Y = np.random.randn(n, no_dims)
        dY = np.zeros((n, no_dims))
        iY = np.zeros((n, no_dims))
        gains = np.ones((n, no_dims))

        # Compute P-values
        P = self.x2p(X, 1e-5, perplexity)
        P = P + np.transpose(P)
        P = P / np.sum(P)
        P = P * 4. # early exaggeration
        P = np.maximum(P, 1e-12)

        # Run iterations
        for iter in range(max_iter):

            # Compute pairwise affinities
            sum_Y = np.sum(np.square(Y), 1)
            num = -2. * np.dot(Y, Y.T)
            num = 1. / (1. + np.add(np.add(num, sum_Y).T, sum_Y))
            num[range(n), range(n)] = 0.
            Q = num / np.sum(num)
            Q = np.maximum(Q, 1e-12)

            # Compute gradient
            PQ = P - Q
            for i in range(n):
                dY[i, :] = np.sum(np.tile(PQ[:, i] * num[:, i], (no_dims, 1)).T * (Y[i, :] - Y), 0)

            # Perform the update
            if iter < 20:
                momentum = initial_momentum
            else:
                momentum = final_momentum
            gains = (gains + 0.2) * ((dY > 0.) != (iY > 0.)) + \
                    (gains * 0.8) * ((dY > 0.) == (iY > 0.))
            gains[gains < min_gain] = min_gain
            iY = momentum * iY - eta * (gains * dY)
            Y = Y + iY
            Y = Y - np.tile(np.mean(Y, 0), (n, 1))

            # Compute current value of cost function
            if (iter + 1) % 10 == 0:
                C = np.sum(P * np.log(P / Q))
                print("Iteration %d: error is %f" % (iter + 1, C))

            # Stop lying about P-values
            if iter == 100:
                P = P / 4.

        # Return solution
        return Y


class PCA(object):
    """
    A PCA module for data analysis.

    Parameters
    ----------
    n_components: int, default is 20.
        number of remain dimensions after PCA analysis

    Attributes
    ----------
    trained_: bool,
        whether the pca object has been trained
    X_transformed_: numpy ndarray, shape=[N, M]
        the transformed X dataset,
        N is number of samples, M is the reduced dimensions,
        M = n_components
    scaled_: bool,
        whether the X dataset has been scaled. It is required for
        PCA calculation.
    scaler_: sklearn preprocessing StandardScaler object
        the scaler object
    X_scaled_: numpy ndarray, shape=[N, M]
        the scaled X dataset,
        N is number of samples, M is the number of dimensions
    pca_obj: sklearn decomposition PCA object,
        the pca object
    eigvalues_: numpy array,
        the eigvalues of the new axis
    eigvalues_ratio: numpy array,
        the percentage ratio of the new axis variances
    eigvectors_: numpy ndarray,
        # TODO: to to completed here

    Methods
    -------
    fit
    transform
    eigvalues
    eigvectors

    """

    def __init__(self, n_components=20):
        self.n_components = n_components

        # attributes
        self.trained_ = False
        self.X_transformed_ = None

        self.scaled_ = False
        self.scaler_ = None
        self.X_scaled = None

        self.pca_obj = None
        self.eigvalues_ = None
        self.eigvalues_ratio_ = None
        self.eigvectors_ = None

    def fit(self, X):
        """
        fit a pca object

        Parameters
        ----------
        X: numpy ndarray, shape = [N, M]
            the input data matrix, N is the number of samples
            M is the number of dimensions

        Returns
        -------
        pca_obj: sklearn.decomposition.PCA object
            the pca object from sklearn

        """

        if self.scaled_:
            Xs = X
        else:
            print("Dataset not scaled. Scaling the dataset now ...... ")
            self.scaler_ = sklearn.preprocessing.StandardScaler()
            Xs = self.scaler_.fit_transform(X)

            self.scaled_ = True
        self.X_scaled = Xs

        # using sklearn, perform PCA analysis based on scaled dataset
        print("Perform PCA decompostion now ...... ")
        pca_obj = decomposition.PCA(n_components=self.n_components)
        pca_obj.fit(self.X_scaled)

        # train and transform the dataset
        print("Transform dataset now ...... ")
        self.X_transformed_ = pca_obj.transform(X)
        self.trained_ = True

        self.pca_obj = pca_obj

        # get eigval and eigvect
        print("Obtain eigvalues and eigvectors ...... ")
        self.eigvalues()
        self.eigvectors()

        return pca_obj

    def transform(self, X):
        """

        Parameters
        ----------
        X: numpy, ndarray, shape = [ N, M]
            the input dataset, N is number of samples,
            M is number of dimensions

        Returns
        -------
        X_transformed: numpy, ndarray, shape=[N, M_1]
            transformed dataset, N is number of samples
            M_1 is number of reduced dimensions, M_1 == n_components

        """

        if self.trained_:
            return self.pca_obj.transform(X)
        else:
            print("Your pca object is not trained yet. Training it now ...")
            pca_obj = self.fit(X)

            return pca_obj.transform(X)

    def eigvalues(self):
        """
        Eigen values, the variance of the eigenvectors

        Returns
        -------
        eigval_: numpy array, shape=[1, M]
            the eigvalues, M is number of reduced dimensions.
            M == n_components

        """

        eigval_ = self.pca_obj.explained_variance_

        self.eigvalues_ = eigval_
        self.eigvalues_ratio_ = self.pca_obj.explained_variance_ratio_

        return None

    def eigvectors(self):
        """
        Eigenvectors. This vectors could be applied for essential dynamics
        analysis.

        Returns
        -------
        eigvect_: numpy ndarray, shape=[M_1, M]
            # TODO: add further explanations here

        """

        eigvect_ = self.pca_obj.components_

        self.eigvectors_ = eigvect_

        return None


def datset_subset(dat, begin, end):
    """
    Subset a dataset given the index range

    Parameters
    ----------
    dat: pandas DataFrame,
        the dataset for subsetting
    begin: int,
        the beginning index
    end:
        the ending index

    Returns
    -------
    X: pandas DataFrame,
        the processed dataset

    """

    # TODO: add a check whether the datatype is pandas dataframe

    X = dat.copy

    # slice the dataset
    if begin > 0:
        X = X[X.index >= begin]
    if end > 0 and end > begin:
        X = X[X.index <= begin]

    return X


def iterload_xyz_coordinates(xtcfile, top, chunk, stride, atom_selection="name CA"):
    """
    Load a large gromacs xtc trajectory file using mdtraj.iterload method, and extract
    the atom xyz coordinates.

    Parameters
    ----------
    xtcfile: str, format gromacs xtc
        the gromacs xtc trajectory file
    top: str, format pdb
        the reference pdb file
    chunk: int,
        number of frames to load per time
    stride: int,
        skip n frames when loading trajectory file
    atom_selection: str,
        the atom selection language

    Returns
    -------
    xyz: pandas dataframe, shape = [N, M]
        the xyz coordinates dataset,
        N is number of samples, or frames
        M is n_atoms * 3

    """

    trajs = gmxcli.read_xtc(xtc=xtcfile, top=top, chunk=chunk, stride=stride)

    xyz = np.array([])

    for traj in trajs:
        copca = cmap.CoordinatesXYZ(traj, top, atom_selection)
        # copca.superimpose()

        if xyz.shape[0] == 0:
            xyz = copca.xyz_coordinates()
        else:
            xyz = np.concatenate((xyz, copca.xyz_coordinates()), axis=0)

    xyz = pd.DataFrame(xyz)

    return xyz


def write_results(X_transformed, variance_ratio, X_out, variance_out, col_index):
    """
    Write PCA results into files:
    1. transformed dataset
    2. explained variance ratio

    Parameters
    ----------
    X_transformed: numpy ndarray
    variance_ratio: numpy array
    X_out: str
    variance_out: str
    dt: int
    col_index: numpy array

    Returns
    -------

    """
    # save the data into a file
    dat = pd.DataFrame(X_transformed)
    dat.index = col_index
    #dat.index = np.arange(X_transformed.shape[0]) * dt
    dat.columns = ["PC_%d" % x for x in np.arange(X_transformed.shape[1])]
    dat.to_csv(X_out, sep=",", header=True, index=True,
               index_label="time(ps)", float_format="%.3f")

    # save variance ratio into a file
    variance = list(variance_ratio)
    eigval = pd.DataFrame()
    eigval["PC"] = np.arange(len(variance))
    eigval["eigval_ratio"] = variance
    eigval.to_csv(variance_out, sep=",", header=True, index=False, float_format="%.3f")

    return None


def load_dataset(fn, skip_index=True, sep=","):
    """
    Load a dataset file.

    Parameters
    ----------
    fn: str,
        input dataset file name, a csv comma separated file
    skip_index: bool,
        whether skip the first col and using it as index
    sep: str,
        the delimiter or spacer in the dataset file

    Returns
    -------
    X: pandas DataFrame, shape=[N, M]
        N is number of samples, M is the number of dimensions.

    """

    # load dataset, assign the index information
    if skip_index:
        X = pd.read_csv(fn, sep=",", header=0, index_col=0)
    else:
        X = pd.read_csv(fn, sep=",", header=0)

    return X


def run_pca(dat, proj=10, output="transformed.csv", var_ratio_out="variance_explained.dat"):
    """
    Perform PCA calculation given a clean dataset file.

    Parameters
    ----------
    dat: pandas DataFrame, or a numpy ndarray, shape=[N, M]
        N is the number of samples, M is the number of dimensions.
    proj: int,
        number of projections to output
    output: str,
        the transformed or projected dataset output file name, format is csv
    var_ratio_out: str,
        the variance explained ratio of the eigvalues output file name

    Returns
    -------

    """

    index_col = dat.index

    # calculate PCA
    pca = PCA(n_components=proj)
    pca.fit(dat)

    # get transformed dataset
    X_transformed = pca.X_transformed_
    variance_ratio = pca.eigvalues_ratio_

    # write result
    write_results(X_transformed=X_transformed, variance_ratio=variance_ratio,
                  X_out=output, variance_out=var_ratio_out, col_index=index_col)
    return None


def iterload_cmap(args):
    """
    Load a trajectory file and calculate the atom contactmap.

    Parameters
    ----------
    args: argparse object
        the argument options

    Returns
    -------

    """

    # TODO: add a residue based selection module here

    atoms_selections = args.selct.split()
    if len(atoms_selections) == 2:
        atoms_selections = atoms_selections
    else:
        atoms_selections = [atoms_selections[0]] * 2

    top = mt.load(args.s).topology

    atom_grp_a = top.select("name %s" % atoms_selections[0])
    atom_grp_b = top.select("name %s" % atoms_selections[1])

    trajs = gmxcli.read_xtc(xtc=args.f, top=args.s, chunk=1000, stride=int(args.dt/args.ps))

    cmap_dat = np.array([])

    for traj in trajs:
        contmap = cmap.ContactMap(traj=traj, group_a=atom_grp_a, group_b=atom_grp_b, cutoff=args.cutoff)

        if cmap_dat.shape[0] == 0:
            cmap_dat = contmap.cmap_
        else:
            cmap_dat = np.concatenate((cmap_dat, contmap.cmap_), axis=1)

    cmap_dat = pd.DataFrame(cmap_dat)

    return cmap_dat


def cmap_pca(args):
    """
    Perform PCA calculation based on contact map between atoms along the
    trajectory.

    Parameters
    ----------
    args: argparse object,
        the arguments options

    Returns
    -------

    """

    # contmap is a pd.DataFrame containing the contact map information
    contmap = iterload_cmap(args)
    contmap.index = np.arange(contmap.shape[0]) * args.dt

    # process the begin end information
    contmap = datset_subset(contmap, begin=args.b, end=args.e)

    # run pca and write result to outputs
    run_pca(contmap, proj=args.proj, output=args.o, var_ratio_out=args.var_ratio)


def general_pca(args):
    """
    Perform PCA calculation based on an input dataset file (preferably a csv file).

    Parameters
    ----------
    args: argparse object,
        the arguments options

    Returns
    -------

    """

    # dat is a pd.DataFrame with index information
    dat = load_dataset(args.f, args.skip_index)

    # process the begin end information
    dat = datset_subset(dat, begin=args.b, end=args.e)

    # run pca and write result to outputs
    run_pca(dat, proj=args.proj, output=args.o, var_ratio_out=args.var_ratio)

    return None

def xyz_pca(args):
    """
    Perform xyz coordinate based PCA calculation based on Gromacs XTC files.


    Parameters
    ----------
    args: argparse object,
        the arguments holder

    Returns
    -------

    """

    if args.v:
        print("Start to load trajectory file ...... ")

    # obtain all xyz coordinates in a long trajectory file
    dat = iterload_xyz_coordinates(xtcfile=args.f, top=args.s,
                                   chunk=10000, stride=int(args.dt/args.ps),
                                   atom_selection=args.select)

    # add time index into dataframe
    # dat = pd.DataFrame(xyz)
    dat.index = np.arange(dat.shape[0]) * args.dt

    # process the begin end information
    dat = datset_subset(dat, begin=args.b, end=args.e)

    # run pca and write result to outputs
    run_pca(dat, proj=args.proj, output=args.o, var_ratio_out=args.var_ratio)


def arguments():
    # prepare gmx style argument for pca calculation
    d = """
    Perform PCA analysis of the xyz coordinates of selected atoms

    Example: 
    Print help information
    gmx_pca.py -h

    """
    parser = gmxcli.GromacsCommanLine(d=d)

    parser.arguments()

    parser.parser.add_argument("-mode", type=str, default="general",
                               help="Input, optional. \n"
                                    "The PCA calculation mode. \n"
                                    "Options: general, xyz, cmap \n"
                                    "general: perform general PCA using a well formated dataset file. \n"
                                    "xyz: perform xyz coordinate PCA analysis using a trajectory xtc file. \n"
                                    "cmap: perform contact map PCA analysis using a trajectory xtc file. ")
    parser.parser.add_argument("-cutoff", default=0.35, type=float,
                               help="Input, optional, it works with mode =cmap \n"
                                    "The distance cutoff for contactmap calculation. Unit is nanometer.\n"
                                    "Default is 0.35. ")
    parser.parser.add_argument("-proj", type=int, default=2,
                               help="Input, optional. \n"
                                    "How many number of dimensions to output. \n"
                                    "Default is 2.")
    parser.parser.add_argument("-select", type=str, default="name CA",
                               help="Input, optional, it works with mode = xyz \n"
                                    "Atom selected for PCA calculation. \n"
                                    "Default is name CA.")
    parser.parser.add_argument("-var_ratio", type=str, default="explained_variance_ratio.dat",
                               help="Output, optional. \n"
                                    "Output file name containing explained eigen values variance ratio. \n"
                                    "Default is explained_variance_ratio.dat. ")
    parser.parser.add_argument("-skip_index", type=lambda x: (str(x).lower() == "true"), default=True,
                               help="Input, optional. Working with mode == general \n"
                                    "Generally, there would be an index column in the input file, choose\n"
                                    "to whether skip the index column. Default is True. ")

    parser.parse_arguments()
    args = parser.args

    return args


def gmxpca():

    args = arguments()

    if args.mode == "xyz":
        xyz_pca(args=args)

        return None

    elif args.mode == "general":
        general_pca(args=args)

        return None

    elif args.mode == "cmap":
        # TODO: to be completed.
        cmap_pca(args=args)

        return None

