import pickle
import numpy as np
import matplotlib.pyplot as plt  # To visualize
from sklearn.linear_model import LinearRegression
import matplotlib as mpl

X = None
Y = None
X_content = None
Y_content = None
with open("x.txt", "rb") as fp:   # Unpickling
    Y = pickle.load(fp)

with open("y.txt", "rb") as fp:   # Unpickling
    X = pickle.load(fp)

with open("x_content.txt", "rb") as fp:   # Unpickling
    Y_content = pickle.load(fp)

with open("y_content.txt", "rb") as fp:   # Unpickling
    X_content = pickle.load(fp)

X = np.array(X) * 100
Y = np.array(Y) * 100
X_content = np.array(X_content) * 100
Y_content = np.array(Y_content) * 100
print(X)

x_comb = np.append(X, X_content).reshape(-1, 1)
y_comb = np.append(Y, Y_content).reshape(-1, 1)
print(x_comb)
linear_regressor_comb = LinearRegression()  # create object for the class
linear_regressor_comb.fit(x_comb, y_comb)  # perform linear regression
Y_pred_comb = linear_regressor_comb.predict(x_comb)  # make predictions
rscore_comb = round(linear_regressor_comb.score(x_comb, y_comb), 4)

# seaborn-paper
plotstyle = "seaborn"
plt.style.use(plotstyle)

# fig = plt.figure(figsize=(10, 4))
fig = plt.figure()

ax = fig.add_subplot(111)
ax.yaxis.set_major_formatter(mpl.ticker.StrMethodFormatter('${x:,.0f}'))
ax.xaxis.set_major_formatter(mpl.ticker.StrMethodFormatter('${x:,.0f}'))

ax.scatter(X, Y, label="Structural damage", s=20,
           facecolors='none', edgecolors='black', alpha=0.75)
ax.scatter(X_content, Y_content, label='Content damage', s=20,
           facecolors='none', edgecolors='r', alpha=0.75, marker="s")
ax.plot(x_comb, Y_pred_comb, linestyle='dashed',
        color='black', label=f'R2={rscore_comb}', linewidth=1)

# plt.annotate('n=987', xy=(0.8, 0.7), xycoords='axes fraction', fontsize='small')

axes = plt.gca()
axes.set_xlim([0, 155000])
axes.set_ylim([0, 155000])

plt.ylabel('ER2 Flood')
plt.xlabel('Hazus')
plt.legend()
fig.savefig(f'damages-{plotstyle}.png', bbox_inches="tight", dpi=300)
plt.show()
