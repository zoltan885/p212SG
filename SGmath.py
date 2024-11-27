
import numpy as np
import lmfit


## FOR TESTING
def gaussian(x, mu, sig, noise=0):
    y = (1.0 / (np.sqrt(2.0 * np.pi) * sig) * np.exp(-np.power((x - mu) / sig, 2.0) / 2))
    y_n = y + noise * np.random.normal(size=y.shape)
    return x, y_n


def fit_gaussian(x, y, bg=None):
    """
    Fits a Gaussian model to the given data, optionally with a background model.
    Parameters:
    x (array-like): The independent variable data.
    y (array-like): The dependent variable data.
    bg (str, optional): The type of background model to include. 
                        Can be 'constant', 'linear', or None. Default is None.
    Returns:
    lmfit.model.ModelResult: The result of the fit, or None if the fit failed.
    Raises:
    AssertionError: If bg is not one of None, 'constant', or 'linear'.
    """
    assert bg in [None, 'constant', 'linear'], f'bg must be None, constant or linear, not {bg}'
    
    gmod = lmfit.models.GaussianModel(prefix='peak_')
    if bg == 'linear':
        bgmod = lmfit.models.LinearModel(prefix='line_')
    elif bg == 'constant':
        bgmod = lmfit.models.ConstantModel(prefix='const_')
    
    try:
        pars = gmod.guess(y, x=x)
        if bg is not None:
            pars += bgmod.guess(y, x=x)
    except:
        print('Automatic parameter guess failed')
        pars = gmod.make_params()
        pars += bgmod.make_params()
        # peak_center parameter is restricted to the data region
        pars['peak_center'].set(x[np.argmax(y)], min = np.min(x), max = np.max(x))
        pars['peak_amplitude'].set(np.max(y)-np.min(y))
        pars['peak_sigma'].set(0.2*(np.max(x)-np.min(x)))
        if bgmod == 'constant':
            pars['const_c'].set(np.min(y))
        if bgmod == 'linear':
            pars['line_slope'].set((y[-1]-y[0])/(x[-1]-x[0]))
            pars['line_intercept'].set(np.min(y))
    
    # constraining the peak center to the data region
    pars['peak_center'].set(min = np.min(x), max = np.max(x))

    model = gmod
    if bg is not None:
        model += bgmod
    try:
        result = model.fit(y, pars, x=x)
    except:
        print('Fit failed')
        return None
    return result

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        sys.exit('This is a module. For testing use: python SGmath.py --test')
    if sys.argv[1] != '--test':
        sys.exit('This is a module. For testing use: python SGmath.py --test')
    if sys.argv[1] == '--test':
        import matplotlib.pyplot as plt
        # subplots would be better
        x, y = gaussian(np.linspace(-10, 10, 100), 0, 1, 0.1)
        result = fit_gaussian(x, y)
        print(result.fit_report())
        result.plot_fit()
        plt.show()
        
        x, y = gaussian(np.linspace(-10, 10, 100), 0, 1, 0.1)
        result = fit_gaussian(x, y, bg='linear')
        print(result.fit_report())
        result.plot_fit()
        plt.show()
        
        x, y = gaussian(np.linspace(-10, 10, 100), 0, 1, 0.1)
        result = fit_gaussian(x, y, bg='constant')
        print(result.fit_report())
        result.plot_fit()
        plt.show()
        
        x, y = gaussian(np.linspace(-10, 10, 100), 0, 1, 0.1)
        result = fit_gaussian(x, y, bg='constant')
        print(result.fit_report())
        result.plot_fit()
        plt.show()
        
        x, y = gaussian(np.linspace(-10, 10, 100), 0, 1, 0.1)
        result = fit_gaussian(x, y, bg='constant')
        print(result.fit_report())
        result.plot_fit()
        plt.show()
        
        x, y = gaussian(np.linspace(-10, 10, 100), 0, 2, 0.05)
        result = fit_gaussian(x, y, bg='constant')
        print(result.fit_report())
        result.plot_fit()
        plt.show()
        
        x, y = gaussian(np.linspace(-10, 10, 100), -2, 2, 0.03)
        result = fit_gaussian(x, y, bg='constant')
        print(result.fit_report())
        result.plot_fit()
        plt.show()
        
        x, y = gaussian(np.linspace(-10, 10, 100), 4, 3, 0.03)
        result = fit_gaussian(x, y, bg='constant')
        print(result.fit_report())
        result.plot_fit()
        plt.show()

        x, y = gaussian(np.linspace(-10, 10, 100), 11, 5, 0.01)
        result = fit_gaussian(x, y, bg='constant')
        print(result.fit_report())
        result.plot_fit()
        plt.show()
    
 