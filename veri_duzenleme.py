import pandas as pd
import numpy as np


df = pd.read_csv('pink_home_urunler.csv')




# Önce TL ve virgül karakterlerini temizleyip float'a çeviriyoruz
df['Fiyat'] = df['eski_fiyat'].str.replace(' TL', '').str.replace('.', '').str.replace(',', '.').astype(float)

# Sonra integer'a çeviriyoruz
df['Fiyat_Int'] = df['Fiyat'].astype(int)
print(df.info())


df.drop(columns=['eski_fiyat','Fiyat_Int'], inplace=True)

df.to_csv("pink_home_urunler.csv")