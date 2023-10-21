
def are_files_identical(file1, file2):
    with open(file1, 'rb') as file1, open(file2, 'rb') as file2:
        # Read the contents of both files
        content1 = file1.read()
        content2 = file2.read()

        # Compare the contents
        if content1 == content2:
            return True
        else:
            return False