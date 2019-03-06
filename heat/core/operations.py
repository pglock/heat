import itertools
import torch
import numpy as np


from .communication import MPI
from . import stride_tricks
from . import types
from . import tensor

__all__ = [
    'abs',
    'absolute',
    'all',
    'argmin',
    'clip',
    'copy',
    'exp',
    'floor',
    'log',
    'max',
    'min',
    'sin',
    'sqrt',
    'sum',
    'transpose',
    'tril',
    'triu',
    'add',
    'sub',
    'div',
    'mul',
    'pow',
    'eq',
    'equal',
    'ne',
    'lt',
    'le',
    'gt',
    'ge'
]


def abs(x, out=None, dtype=None):
    """
    Calculate the absolute value element-wise.

    Parameters
    ----------
    x : ht.tensor
        The values for which the compute the absolute value.
    out : ht.tensor, optional
        A location into which the result is stored. If provided, it must have a shape that the inputs broadcast to.
        If not provided or None, a freshly-allocated array is returned.
    dtype : ht.type, optional
        Determines the data type of the output array. The values are cast to this type with potential loss of
        precision.

    Returns
    -------
    absolute_values : ht.tensor
        A tensor containing the absolute value of each element in x.
    """
    if dtype is not None and not issubclass(dtype, types.generic):
        raise TypeError('dtype must be a heat data type')

    absolute_values = __local_operation(torch.abs, x, out)
    if dtype is not None:
        absolute_values._tensor__array = absolute_values._tensor__array.type(
            dtype.torch_type())
        absolute_values._tensor__dtype = dtype

    return absolute_values


def absolute(x, out=None, dtype=None):
    """
    Calculate the absolute value element-wise.

    np.abs is a shorthand for this function.

    Parameters
    ----------
    x : ht.tensor
        The values for which the compute the absolute value.
    out : ht.tensor, optional
        A location into which the result is stored. If provided, it must have a shape that the inputs broadcast to.
        If not provided or None, a freshly-allocated array is returned.
    dtype : ht.type, optional
        Determines the data type of the output array. The values are cast to this type with potential loss of
        precision.

    Returns
    -------
    absolute_values : ht.tensor
        A tensor containing the absolute value of each element in x.
    """
    return abs(x, out, dtype)


def all(x, axis=None, out=None):
    """
    Test whether all array elements along a given axis evaluate to True.

    Parameters:
    -----------

    x : ht.tensor
        Input array or object that can be converted to an array.

    axis : None or int, optional #TODO: tuple of ints, issue #67
        Axis or along which a logical AND reduction is performed. The default (axis = None) is to perform a 
        logical AND over all the dimensions of the input array. axis may be negative, in which case it counts 
        from the last to the first axis.

    out : ht.tensor, optional
        Alternate output array in which to place the result. It must have the same shape as the expected output 
        and its type is preserved.

    Returns:	
    --------
    all : ht.tensor, bool

    A new boolean or ht.tensor is returned unless out is specified, in which case a reference to out is returned.

    Examples:
    ---------
    >>> import heat as ht
    >>> a = ht.random.randn(4, 5)
    >>> a
    tensor([[ 0.5370, -0.4117, -3.1062,  0.4897, -0.3231],
            [-0.5005, -1.7746,  0.8515, -0.9494, -0.2238],
            [-0.0444,  0.3388,  0.6805, -1.3856,  0.5422],
            [ 0.3184,  0.0185,  0.5256, -1.1653, -0.1665]])
    >>> x = a < 0.5
    >>> x
    tensor([[0, 1, 1, 1, 1],
            [1, 1, 0, 1, 1],
            [1, 1, 0, 1, 0],
            [1, 1, 0, 1, 1]], dtype=ht.uint8)
    >>> ht.all(x)
    tensor([0], dtype=ht.uint8)
    >>> ht.all(x, axis=0)
    tensor([[0, 1, 0, 1, 0]], dtype=ht.uint8)
    >>> ht.all(x, axis=1)
    tensor([[0],
            [0],
            [0],
            [0]], dtype=ht.uint8)

    Write out to predefined buffer:
    >>> out = ht.zeros((1, 5))
    >>> ht.all(x, axis=0, out=out)
    >>> out
    tensor([[0, 1, 0, 1, 0]], dtype=ht.uint8)
    """
    # TODO: make me more numpy API complete. Issue #101
    return __reduce_op(x, lambda t, *args, **kwargs: t.byte().all(*args, **kwargs), MPI.LAND, axis, out=out)


def argmin(x, axis=None, out=None):
    """
    Returns the indices of the minimum values along an axis.

    Parameters:
    ----------
    x : ht.tensor
        Input array.
    axis : int, optional
        By default, the index is into the flattened tensor, otherwise along the specified axis.
    # TODO out : ht.tensor, optional. Issue #100
        If provided, the result will be inserted into this tensor. It should be of the appropriate shape and dtype.

    Returns:
    -------
    index_tensor : ht.tensor of ints
        Array of indices into the array. It has the same shape as x.shape with the dimension along axis removed.

    Examples:
    --------
    >>> a = ht.randn(3,3)
    >>> a
    tensor([[-1.7297,  0.2541, -0.1044],
            [ 1.0865, -0.4415,  1.3716],
            [-0.0827,  1.0215, -2.0176]])
    >>> ht.argmin(a)
    tensor([8])
    >>> ht.argmin(a, axis=0)
    tensor([[0, 1, 2]])
    >>> ht.argmin(a, axis=1)
    tensor([[0],
            [1],
            [2]])
    """
    axis = stride_tricks.sanitize_axis(x.shape, axis)

    if axis is None:
        # TEMPORARY SOLUTION! TODO: implementation for axis=None, distributed tensor Issue #100
        # perform sanitation
        if not isinstance(x, tensor.tensor):
            raise TypeError('expected x to be a ht.tensor, but was {}'.format(type(x)))

        out = torch.reshape(torch.argmin(x._tensor__array), (1,))
        return tensor.tensor(out, out.shape, types.canonical_heat_type(out.dtype), None, x.device, x.comm)

    out = __reduce_op(x, torch.min, MPI.MIN, axis, out=None)._tensor__array[1]

    return tensor.tensor(out, out.shape, types.canonical_heat_type(out.dtype), x.split, x.device, x.comm)


def clip(a, a_min, a_max, out=None):
    """
    Parameters
    ----------
    a : ht.tensor
        Array containing elements to clip.
    a_min : scalar or None
        Minimum value. If None, clipping is not performed on lower interval edge. Not more than one of a_min and
        a_max may be None.
    a_max : scalar or None
        Maximum value. If None, clipping is not performed on upper interval edge. Not more than one of a_min and
        a_max may be None.
    out : ht.tensor, optional
        The results will be placed in this array. It may be the input array for in-place clipping. out must be of
        the right shape to hold the output. Its type is preserved.

    Returns
    -------
    clipped_values : ht.tensor
        A tensor with the elements of this tensor, but where values < a_min are replaced with a_min, and those >
        a_max with a_max.
    """
    if not isinstance(a, tensor.tensor):
        raise TypeError('a must be a tensor')
    if a_min is None and a_max is None:
        raise ValueError('either a_min or a_max must be set')

    if out is None:
        return tensor.tensor(a._tensor__array.clamp(a_min, a_max), a.shape, a.dtype, a.split, a.device, a.comm)
    if not isinstance(out, tensor.tensor):
        raise TypeError('out must be a tensor')

    return a._tensor__array.clamp(a_min, a_max, out=out._tensor__array) and out


def copy(a):
    """
    Return an array copy of the given object.

    Parameters
    ----------
    a : ht.tensor
        Input data to be copied.

    Returns
    -------
    copied : ht.tensor
        A copy of the original
    """
    if not isinstance(a, tensor.tensor):
        raise TypeError('input needs to be a tensor')
    return tensor.tensor(a._tensor__array.clone(), a.shape, a.dtype, a.split, a.device, a.comm)


def exp(x, out=None):
    """
    Calculate the exponential of all elements in the input array.

    Parameters
    ----------
    x : ht.tensor
        The value for which to compute the exponential.
    out : ht.tensor or None, optional
        A location in which to store the results. If provided, it must have a broadcastable shape. If not provided
        or set to None, a fresh tensor is allocated.

    Returns
    -------
    exponentials : ht.tensor
        A tensor of the same shape as x, containing the positive exponentials of each element in this tensor. If out
        was provided, logarithms is a reference to it.

    Examples
    --------
    >>> ht.exp(ht.arange(5))
    tensor([ 1.0000,  2.7183,  7.3891, 20.0855, 54.5981])
    """
    return __local_operation(torch.exp, x, out)


def floor(x, out=None):
    """
    Return the floor of the input, element-wise.

    The floor of the scalar x is the largest integer i, such that i <= x. It is often denoted as \lfloor x \rfloor.

    Parameters
    ----------
    x : ht.tensor
        The value for which to compute the floored values.
    out : ht.tensor or None, optional
        A location in which to store the results. If provided, it must have a broadcastable shape. If not provided
        or set to None, a fresh tensor is allocated.

    Returns
    -------
    floored : ht.tensor
        A tensor of the same shape as x, containing the floored valued of each element in this tensor. If out was
        provided, logarithms is a reference to it.

    Examples
    --------
    >>> ht.floor(ht.arange(-2.0, 2.0, 0.4))
    tensor([-2., -2., -2., -1., -1.,  0.,  0.,  0.,  1.,  1.])
    """
    return __local_operation(torch.floor, x, out)


def log(x, out=None):
    """
    Natural logarithm, element-wise.

    The natural logarithm log is the inverse of the exponential function, so that log(exp(x)) = x. The natural
    logarithm is logarithm in base e.

    Parameters
    ----------
    x : ht.tensor
        The value for which to compute the logarithm.
    out : ht.tensor or None, optional
        A location in which to store the results. If provided, it must have a broadcastable shape. If not provided
        or set to None, a fresh tensor is allocated.

    Returns
    -------
    logarithms : ht.tensor
        A tensor of the same shape as x, containing the positive logarithms of each element in this tensor.
        Negative input elements are returned as nan. If out was provided, logarithms is a reference to it.

    Examples
    --------
    >>> ht.log(ht.arange(5))
    tensor([  -inf, 0.0000, 0.6931, 1.0986, 1.3863])
    """
    return __local_operation(torch.log, x, out)


def max(x, axis=None, out=None):
    # TODO: initial : scalar, optional Issue #101
    """
    Return the maximum along a given axis.

    Parameters
    ----------
    a : ht.tensor
        Input data.
    axis : None or int, optional
        Axis or axes along which to operate. By default, flattened input is used.
    out : ht.tensor, optional
        Tuple of two output tensors (max, max_indices). Must be of the same shape and buffer length as the expected
        output. The minimum value of an output element. Must be present to allow computation on empty slice.

    Examples
    --------
    >>> a = ht.float32([
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
            [10, 11, 12]
        ])
    >>> ht.max(a)
    tensor([12.])
    >>> ht.min(a, axis=0)
    tensor([[10., 11., 12.]])
    >>> ht.min(a, axis=1)
    tensor([[ 3.],
        [ 6.],
        [ 9.],
        [12.]])
    """
    def local_max(*args, **kwargs):
        result = torch.max(*args, **kwargs)
        if isinstance(result, tuple):
            return result[0]
        return result

    return __reduce_op(x, local_max, MPI.MAX, axis, out)


def min(x, axis=None, out=None):
    # TODO: initial : scalar, optional Issue #101
    """
    Return the minimum along a given axis.

    Parameters
    ----------
    a : ht.tensor
        Input data.
    axis : None or int
        Axis or axes along which to operate. By default, flattened input is used.
    out : ht.tensor, optional
        Tuple of two output tensors (min, min_indices). Must be of the same shape and buffer length as the expected
        output.The maximum value of an output element. Must be present to allow computation on empty slice.

    Examples
    --------
    >>> a = ht.float32([
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
            [10, 11, 12]
        ])
    >>> ht.min(a)
    tensor([1.])
    >>> ht.min(a, axis=0)
    tensor([[1., 2., 3.]])
    >>> ht.min(a, axis=1)
    tensor([[ 1.],
        [ 4.],
        [ 7.],
        [10.]])
    """
    def local_min(*args, **kwargs):
        result = torch.min(*args, **kwargs)
        if isinstance(result, tuple):
            return result[0]
        return result

    return __reduce_op(x, local_min, MPI.MIN, axis, out)


def sin(x, out=None):
    """
    Return the trigonometric sine, element-wise.

    Parameters
    ----------
    x : ht.tensor
        The value for which to compute the trigonometric sine.
    out : ht.tensor or None, optional
        A location in which to store the results. If provided, it must have a broadcastable shape. If not provided
        or set to None, a fresh tensor is allocated.

    Returns
    -------
    sine : ht.tensor
        A tensor of the same shape as x, containing the trigonometric sine of each element in this tensor.
        Negative input elements are returned as nan. If out was provided, square_roots is a reference to it.

    Examples
    --------
    >>> ht.sin(ht.arange(-6, 7, 2))
    tensor([ 0.2794,  0.7568, -0.9093,  0.0000,  0.9093, -0.7568, -0.2794])
    """
    return __local_operation(torch.sin, x, out)


def sqrt(x, out=None):
    """
    Return the non-negative square-root of a tensor element-wise.

    Parameters
    ----------
    x : ht.tensor
        The value for which to compute the square-roots.
    out : ht.tensor or None, optional
        A location in which to store the results. If provided, it must have a broadcastable shape. If not provided or
        set to None, a fresh tensor is allocated.

    Returns
    -------
    square_roots : ht.tensor
        A tensor of the same shape as x, containing the positive square-root of each element in x. Negative input
        elements are returned as nan. If out was provided, square_roots is a reference to it.

    Examples
    --------
    >>> ht.sqrt(ht.arange(5))
    tensor([0.0000, 1.0000, 1.4142, 1.7321, 2.0000])
    >>> ht.sqrt(ht.arange(-5, 0))
    tensor([nan, nan, nan, nan, nan])
    """
    return __local_operation(torch.sqrt, x, out)


def sum(x, axis=None, out=None):
    """
    Sum of array elements over a given axis.

    Parameters
    ----------
    x : ht.tensor
        Input data.

    axis : None or int, optional
        Axis along which a sum is performed. The default, axis=None, will sum
        all of the elements of the input array. If axis is negative it counts 
        from the last to the first axis.

    Returns
    -------
    sum_along_axis : ht.tensor
        An array with the same shape as self.__array except for the specified axis which 
        becomes one, e.g. a.shape = (1, 2, 3) => ht.ones((1, 2, 3)).sum(axis=1).shape = (1, 1, 3)

    Examples
    --------
    >>> ht.sum(ht.ones(2))
    tensor([2.])

    >>> ht.sum(ht.ones((3,3)))
    tensor([9.])

    >>> ht.sum(ht.ones((3,3)).astype(ht.int))
    tensor([9])

    >>> ht.sum(ht.ones((3,2,1)), axis=-3)
    tensor([[[3.],
            [3.]]])
    """
    # TODO: make me more numpy API complete Issue #101
    return __reduce_op(x, torch.sum, MPI.SUM, axis, out)

  
def transpose(a, axes=None):
    """
    Permute the dimensions of an array.

    Parameters
    ----------
    a : array_like
        Input array.
    axes : None or list of ints, optional
        By default, reverse the dimensions, otherwise permute the axes according to the values given.

    Returns
    -------
    p : ht.tensor
        a with its axes permuted.
    """
    # type check the input tensor
    if not isinstance(a, tensor.tensor):
        raise TypeError('a must be of type ht.tensor, but was {}'.format(type(a)))

    # set default value for axes permutations
    dimensions = len(a.shape)
    if axes is None:
        axes = tuple(reversed(range(dimensions)))
    # if given, sanitize the input
    else:
        try:
            # convert to a list to allow index access
            axes = list(axes)
        except TypeError:
            raise ValueError('axes must be an iterable containing ints')

        if len(axes) != dimensions:
            raise ValueError('axes do not match tensor shape')
        for index, axis in enumerate(axes):
            if not isinstance(axis, int):
                raise TypeError('axis must be an integer, but was {}'.format(type(axis)))
            elif axis < 0:
                axes[index] = axis + dimensions

    # infer the new split axis, it is the position of the split axis within the new axes permutation
    try:
        transposed_split = axes.index(a.split) if a.split is not None else None
    except ValueError:
        raise ValueError('axes do not match tensor shape')

    # try to rearrange the tensor and return a new transposed variant
    try:
        transposed_data = a._tensor__array.permute(*axes)
        transposed_shape = tuple(a.shape[axis] for axis in axes)

        return tensor.tensor(transposed_data, transposed_shape, a.dtype, transposed_split, a.device, a.comm)
    # if not possible re- raise any torch exception as ValueError
    except RuntimeError as exception:
        raise ValueError(str(exception))


# statically allocated index slices for non-iterable dimensions in triangular operations
__index_base = (slice(None), slice(None),)


def __tri_op(m, k, op):
    """
    Generic implementation of triangle operations on tensors. It takes care of input sanitation and non-standard
    broadcast behavior of the 2D triangle-operators.

    Parameters
    ----------
    m : ht.tensor
        Input tensor for which to compute the triangle operator.
    k : int, optional
        Diagonal above which to apply the triangle operator, k<0 is below and k>0 is above.
    op : callable
        Implementation of the triangle operator.

    Returns
    -------
    triangle_tensor : ht.tensor
        Tensor with the applied triangle operation

    Raises
    ------
    TypeError
        If the input is not a tensor or the diagonal offset cannot be converted to an integral value.
    """
    if not isinstance(m, tensor.tensor):
        raise TypeError('Expected m to be a tensor but was {}'.format(type(m)))

    try:
        k = int(k)
    except ValueError:
        raise TypeError(
            'Expected k to be integral, but was {}'.format(type(k)))

    # chunk the global shape of the tensor to obtain the offset compared to the other ranks
    offset, _, _ = m.comm.chunk(m.shape, m.split)
    dimensions = len(m.shape)

    # manually repeat the input for vectors
    if dimensions == 1:
        triangle = op(m._tensor__array.expand(m.shape[0], -1), k - offset)
        return tensor.tensor(
            triangle,
            (m.shape[0], m.shape[0],),
            m.dtype,
            None if m.split is None else 1,
            m.device,
            m.comm
        )

    original = m._tensor__array
    output = original.clone()

    # modify k to account for tensor splits
    if m.split is not None:
        if m.split + 1 == dimensions - 1:
            k += offset
        elif m.split == dimensions - 1:
            k -= offset

    # in case of two dimensions we can just forward the call to the callable
    if dimensions == 2:
        op(original, k, out=output)
    # more than two dimensions: iterate over all but the last two to realize 2D broadcasting
    else:
        ranges = [range(elements) for elements in m.lshape[:-2]]
        for partial_index in itertools.product(*ranges):
            index = partial_index + __index_base
            op(original[index], k, out=output[index])

    return tensor.tensor(output, m.shape, m.dtype, m.split, m.device, m.comm)


def tril(m, k=0):
    """
    Returns the lower triangular part of the tensor, the other elements of the result tensor are set to 0.

    The lower triangular part of the tensor is defined as the elements on and below the diagonal.

    The argument k controls which diagonal to consider. If k=0, all elements on and below the main diagonal are
    retained. A positive value includes just as many diagonals above the main diagonal, and similarly a negative
    value excludes just as many diagonals below the main diagonal.

    Parameters
    ----------
    m : ht.tensor
        Input tensor for which to compute the lower triangle.
    k : int, optional
        Diagonal above which to zero elements. k=0 (default) is the main diagonal, k<0 is below and k>0 is above.

    Returns
    -------
    lower_triangle : ht.tensor
        Lower triangle of the input tensor.
    """
    return __tri_op(m, k, torch.tril)


def triu(m, k=0):
    """
    Returns the upper triangular part of the tensor, the other elements of the result tensor are set to 0.

    The upper triangular part of the tensor is defined as the elements on and below the diagonal.

    The argument k controls which diagonal to consider. If k=0, all elements on and below the main diagonal are
    retained. A positive value includes just as many diagonals above the main diagonal, and similarly a negative
    value excludes just as many diagonals below the main diagonal.

    Parameters
    ----------
    m : ht.tensor
        Input tensor for which to compute the upper triangle.
    k : int, optional
        Diagonal above which to zero elements. k=0 (default) is the main diagonal, k<0 is below and k>0 is above.

    Returns
    -------
    upper_triangle : ht.tensor
        Upper triangle of the input tensor.
    """
    return __tri_op(m, k, torch.triu)

def add(t1, t2):
    """
      Element-wise addition of values from two operands, commutative.
      Takes the first and second operand (scalar or tensor) whose elements are to be added as argument.

      Parameters
      ----------
      t1: tensor or scalar
      The first operand involved in the addition

      t2: tensor or scalar
      The second operand involved in the addition


      Returns
      -------
      result: ht.tensor
      A tensor containing the results of element-wise addition of t1 and t2.
      """
    return __binary_op(torch.add, t1, t2)

def sub(t1, t2):
    """
      Element-wise subtraction of values of operand t2 from values of operands t1 (i.e t1 - t2), not commutative.
      Takes the two operands (scalar or tensor) whose elements are to be subtracted (operand 2 from operand 1)
      as argument.

      Parameters
      ----------
      t1: tensor or scalar
      The first operand from which values are subtracted

      t2: tensor or scalar
      The second operand whose values are subtracted


      Returns
      -------
      result: ht.tensor
      A tensor containing the results of element-wise subtraction of t1 and t2.
      """
    return __binary_op(torch.sub, t1, t2)

def div(t1, t2):
    """
        Element-wise true division of values of operand t1 by values of operands t2 (i.e t1 / t2), not commutative.
        Takes the two operands (scalar or tensor) whose elements are to be divided (operand 1 by operand 2)
        as argument.

        Parameters
        ----------
        t1: tensor or scalar
        The first operand whose values are divided

        t2: tensor or scalar
        The second operand by whose values is divided


        Returns
        -------
        result: ht.tensor
        A tensor containing the results of element-wise true division (i.e. floating point values) of t1 by t2.
        """

    return __binary_op(torch.div, t1, t2)

def mul(t1,t2):
    """
      Element-wise multiplication (NOT matrix multiplication) of values from two operands, commutative.
      Takes the first and second operand (scalar or tensor) whose elements are to be multiplied as argument.

      Parameters
      ----------
      t1: tensor or scalar
      The first operand involved in the multiplication

      t2: tensor or scalar
      The second operand involved in the multiplication


      Returns
      -------
      result: ht.tensor
      A tensor containing the results of element-wise multiplication of t1 and t2.
      """

    return __binary_op(torch.mul, t1, t2)

def pow(t1,t2):
    """
        Element-wise exponential function of values of operand t1 to the power of values of operand t2 (i.e t1 ** t2),
        not commutative. Takes the two operands (scalar or tensor) whose elements are to be involved in the exponential
        function(operand 1 to the power of operand 2)
        as argument.

        Parameters
        ----------
        t1: tensor or scalar
        The first operand whose values represent the base

        t2: tensor or scalar
        The second operand by whose values represent the exponent


        Returns
        -------
        result: ht.tensor
        A tensor containing the results of element-wise exponential function.
        """

    return __binary_op(torch.pow, t1, t2)

def eq(t1,t2):
    """
         Element-wise rich comparison of equality between values from two operands, commutative.
         Takes the first and second operand (scalar or tensor) whose elements are to be compared as argument.

         Parameters
         ----------
         t1: tensor or scalar
         The first operand involved in the comparison

         t2: tensor or scalar
         The second operand involved in the comparison

         Returns
         -------
         result: ht.tensor
         A uint8-tensor holding 1 for all elements in which values of t1 are equal to values of t2,
         0 for all other elements
    """

    return __binary_op(torch.eq, t1, t2)

def equal(t1,t2):
    """
         Overall comparison of equality between two tensors. Returns True if two tensors have the same size and elements, and False otherwise.

         Parameters
         ----------
         t1: tensor or scalar
         The first operand involved in the comparison

         t2: tensor or scalar
         The second operand involved in the comparison

         Returns
         -------
         result: bool
         True if t1 and t2 have the same size and elements, False otherwise

    """
    if np.isscalar(t1):

        try:
            t1 = tensor.array([t1])
        except (TypeError,ValueError,):
            raise TypeError('Data type not supported, input was {}'.format(type(t1)))

        if np.isscalar(t2):
            try:
                t2 = tensor.array([t2])
            except (TypeError,ValueError,):
                raise TypeError('Only numeric scalars are supported, but input was {}'.format(type(t2)))


        elif isinstance(t2, tensor.tensor):
            pass
        else:
            raise TypeError('Only tensors and numeric scalars are supported, but input was {}'.format(type(t2)))



    elif isinstance(t1, tensor.tensor):

        if np.isscalar(t2):
            try:
                t2 = tensor.array([t2])
            except (TypeError,ValueError,):
                raise TypeError('Data type not supported, input was {}'.format(type(t2)))

        elif isinstance(t2, tensor.tensor):


            # TODO: implement complex NUMPY rules


            if t2.split is None or t2.split == t1.split:
                pass

            else:
                # It is NOT possible to perform binary operations on tensors with different splits, e.g. split=0 and split=1
                raise NotImplementedError('Not implemented for other splittings')

        else:
            raise TypeError('Only tensors and numeric scalars are supported, but input was {}'.format(type(t2)))


    else:
        raise NotImplementedError('Not implemented for non scalar')


    result = torch.equal(t1._tensor__array, t2._tensor__array)

    return result

def ne(t1,t2):
    """
         Element-wise rich comparison of non-equality between values from two operands, commutative.
         Takes the first and second operand (scalar or tensor) whose elements are to be compared as argument.

         Parameters
         ----------
         t1: tensor or scalar
         The first operand involved in the comparison

         t2: tensor or scalar
         The second operand involved in the comparison

         Returns
         -------
         result: ht.tensor
         A uint8-tensor holding 1 for all elements in which values of t1 are not equal to values of t2,
         0 for all other elements
    """

    return __binary_op(torch.ne, t1, t2)

def lt(t1,t2):
    """
         Element-wise rich less than comparison between values from operand t1 with respect to values of
         operand t2 (i.e. t1 < t2), not commutative.
         Takes the first and second operand (scalar or tensor) whose elements are to be compared as argument.

         Parameters
         ----------
         t1: tensor or scalar
         The first operand to be compared less than second operand

         t2: tensor or scalar
         The second operand to be compared greater than first operand

         Returns
         -------
         result: ht.tensor
          A uint8-tensor holding 1 for all elements in which values of t1 are less than values of t2,
         0 for all other elements
    """

    return __binary_op(torch.lt, t1, t2)

def le(t1,t2):
    """
         Element-wise rich less than or equal comparison between values from operand t1 with respect to values of
         operand t2 (i.e. t1 <= t2), not commutative.
         Takes the first and second operand (scalar or tensor) whose elements are to be compared as argument.

         Parameters
         ----------
         t1: tensor or scalar
         The first operand to be compared less than or equal to second operand

         t2: tensor or scalar
         The second operand to be compared greater than or equal to first operand

         Returns
         -------
         result: ht.tensor
         A uint8-tensor holding 1 for all elements in which values of t1 are less than or equal to values of t2,
         0 for all other elements
    """
    return __binary_op(torch.le, t1, t2)

def gt(t1,t2):
    """
         Element-wise rich greater than comparison between values from operand t1 with respect to values of
         operand t2 (i.e. t1 > t2), not commutative.
         Takes the first and second operand (scalar or tensor) whose elements are to be compared as argument.

         Parameters
         ----------
         t1: tensor or scalar
         The first operand to be compared greater than second operand

         t2: tensor or scalar
         The second operand to be compared less than first operand

         Returns
         -------
         result: ht.tensor
         A uint8-tensor holding 1 for all elements in which values of t1 are greater than values of t2,
         0 for all other elements
    """

    return __binary_op(torch.gt, t1, t2)

def ge(t1,t2):
    """
         Element-wise rich greater than or equal comparison between values from operand t1 with respect to values of
         operand t2 (i.e. t1 >= t2), not commutative.
         Takes the first and second operand (scalar or tensor) whose elements are to be compared as argument.

         Parameters
         ----------
         t1: tensor or scalar
         The first operand to be compared greater than or equal to second operand

         t2: tensor or scalar
         The second operand to be compared less than or equal to first operand

         Returns
         -------
         result: ht.tensor
          A uint8-tensor holding 1 for all elements in which values of t1 are greater than or equal tp values of t2,
         0 for all other elements
    """

    return __binary_op(torch.ge, t1, t2)



def __local_operation(operation, x, out):
    """
    Generic wrapper for local operations, which do not require communication. Accepts the actual operation function as
    argument and takes only care of buffer allocation/writing.

    Parameters
    ----------
    operation : function
        A function implementing the element-wise local operation, e.g. torch.sqrt
    x : ht.tensor
        The value for which to compute 'operation'.
    out : ht.tensor or None
        A location in which to store the results. If provided, it must have a broadcastable shape. If not provided or
        set to None, a fresh tensor is allocated.

    Returns
    -------
    result : ht.tensor
        A tensor of the same shape as x, containing the result of 'operation' for each element in x. If out was
        provided, result is a reference to it.

    Raises
    -------
    TypeError
        If the input is not a tensor or the output is not a tensor or None.
    """
    # perform sanitation
    if not isinstance(x, tensor.tensor):
        raise TypeError('expected x to be a ht.tensor, but was {}'.format(type(x)))
    if out is not None and not isinstance(out, tensor.tensor):
        raise TypeError('expected out to be None or an ht.tensor, but was {}'.format(type(out)))

    # infer the output type of the tensor
    # we need floating point numbers here, due to PyTorch only providing sqrt() implementation for float32/64
    promoted_type = types.promote_types(x.dtype, types.float32)
    torch_type = promoted_type.torch_type()

    # no defined output tensor, return a freshly created one
    if out is None:
        result = operation(x._tensor__array.type(torch_type))
        return tensor.tensor(result, x.gshape, promoted_type, x.split, x.device, x.comm)

    # output buffer writing requires a bit more work
    # we need to determine whether the operands are broadcastable and the multiple of the broadcasting
    # reason: manually repetition for each dimension as PyTorch does not conform to numpy's broadcast semantic
    # PyTorch always recreates the input shape and ignores broadcasting/too large buffers
    broadcast_shape = stride_tricks.broadcast_shape(x.lshape, out.lshape)
    padded_shape = (1,) * (len(broadcast_shape) - len(x.lshape)) + x.lshape
    multiples = [int(a / b) for a, b in zip(broadcast_shape, padded_shape)]
    needs_repetition = any(multiple > 1 for multiple in multiples)

    # do an inplace operation into a provided buffer
    casted = x._tensor__array.type(torch_type)
    operation(casted.repeat(multiples) if needs_repetition else casted, out=out._tensor__array)

    return out


def __reduce_op(x, partial_op, reduction_op, axis, out):
    # TODO: document me Issue #102
    # perform sanitation
    if not isinstance(x, tensor.tensor):
        raise TypeError('expected x to be a ht.tensor, but was {}'.format(type(x)))
    if out is not None and not isinstance(out, tensor.tensor):
        raise TypeError('expected out to be None or an ht.tensor, but was {}'.format(type(out)))

    # no further checking needed, sanitize axis will raise the proper exceptions
    axis = stride_tricks.sanitize_axis(x.shape, axis)
    split = x.split

    if axis is None:
        partial = partial_op(x._tensor__array).reshape((1,))
        output_shape = (1,)
    else:
        partial = partial_op(x._tensor__array, axis, keepdim=True)
        output_shape = x.gshape[:axis] + (1,) + x.gshape[axis + 1:]

    # Check shape of output buffer, if any
    if out is not None and out.shape != output_shape:
        raise ValueError('Expecting output buffer of shape {}, got {}'.format(output_shape, out.shape))

    # perform a reduction operation in case the tensor is distributed across the reduction axis
    if x.split is not None and (axis is None or axis == x.split):
        split = None
        if x.comm.is_distributed():
            x.comm.Allreduce(MPI.IN_PLACE, partial[0], reduction_op)

    if out is not None:
        out._tensor__array = partial
        out._tensor__dtype = types.canonical_heat_type(partial.dtype)
        out._tensor__split = split
        out._tensor__device = x.device
        out._tensor__comm = x.comm

        return out

    return tensor.tensor(
        partial,
        output_shape,
        types.canonical_heat_type(partial[0].dtype),
        split=split,
        device=x.device,
        comm=x.comm
    )


def __binary_op(operation, t1, t2):
    """
    Generic wrapper for element-wise binary operations of two operands (either can be tensor or scalar).
    Takes the operation function and the two operands involved in the operation as arguments.

    Parameters
    ----------
    operation : function
    The operation to be performed. Function that performs operation elements-wise on the involved tensors,
    e.g. add values from other to self

    t1: tensor or scalar
    The first operand involved in the operation,

    t2: tensor or scalar
    The second operand involved in the operation,

    Returns
    -------
    result: ht.tensor
    A tensor containing the results of element-wise operation.
    """


    if np.isscalar(t1):

        try:
            t1 = tensor.array([t1])
        except (ValueError, TypeError,):
            raise TypeError('Data type not supported, input was {}'.format(type(t1)))

        if np.isscalar(t2):
            try:
                t2 = tensor.array([t2])
            except (ValueError, TypeError,):
                raise TypeError('Only numeric scalars are supported, but input was {}'.format(type(t2)))

            output_shape = (1,)
            output_split = None
            output_device = None
            output_comm = None

        elif isinstance(t2, tensor.tensor):
            output_shape = t2.shape
            output_split = t2.split
            output_device = t2.device
            output_comm = t2.comm

        else:
            raise TypeError('Only tensors and numeric scalars are supported, but input was {}'.format(type(t2)))

        if t1.dtype != t2.dtype:
            t1 = t1.astype(t2.dtype)


    elif isinstance(t1, tensor.tensor):

        if np.isscalar(t2):
            try:
                t2 = tensor.array([t2])
            except (ValueError, TypeError,):
                raise TypeError('Data type not supported, input was {}'.format(type(t2)))

        elif isinstance(t2, tensor.tensor):

            output_shape = stride_tricks.broadcast_shape(t1.shape, t2.shape)

            # TODO: implement complex NUMPY rules
            if t2.split is None or t2.split == t1.split:
                pass

            else:
                # It is NOT possible to perform binary operations on tensors with different splits, e.g. split=0 and split=1
                raise NotImplementedError('Not implemented for other splittings')


        else:
            raise TypeError('Only tensors and numeric scalars are supported, but input was {}'.format(type(t2)))

        if t2.dtype != t1.dtype:
            t2 = t2.astype(t1.dtype)

        output_shape = t1.shape
        output_split = t1.split
        output_device = t1.device
        output_comm = t1.comm


    else:
        raise NotImplementedError('Not implemented for non scalar')

    result = operation(t1._tensor__array, t2._tensor__array)

    return tensor.tensor(result, output_shape, t1.dtype, output_split, output_device, output_comm)

