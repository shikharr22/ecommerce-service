from db import test_simple_query

if __name__=="__main__":
    print("testing db connection")
    r=test_simple_query()
    print("result",r)
    